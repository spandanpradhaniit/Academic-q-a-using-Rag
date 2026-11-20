from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import time
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import Document, DocumentChunk
from app.rag import indexing
from app.rag.rerank import get_reranker
from app.services.answers import generate_grounded_answer
from eval.metrics import is_correct_refusal, retrieval_metrics

CONFIG_NAMES = (
    "Vector only",
    "BM25 only",
    "Hybrid weighted",
    "Hybrid RRF + reranker",
)
logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return indexing._tokenize(text)


def load_dataset(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("Dataset must be a JSON object containing a 'cases' array.")
    cases = payload["cases"]
    if not cases:
        raise ValueError("The evaluation dataset contains no cases.")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each evaluation case must be a JSON object.")
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError(f"Dataset case {case.get('id')} has no question.")
        if not isinstance(case.get("in_scope"), bool):
            raise ValueError(f"Dataset case {case.get('id')} must define in_scope.")
        sources = case.get("relevant_sources", [])
        if case["in_scope"] and not sources:
            raise ValueError(f"In-scope case {case.get('id')} needs relevant_sources.")
        if case["in_scope"] and (
            not isinstance(case.get("expected_answer"), str)
            or not case["expected_answer"].strip()
        ):
            raise ValueError(f"In-scope case {case.get('id')} needs an expected_answer.")
        if case["in_scope"] and any(
            not isinstance(source, dict)
            or not isinstance(source.get("document_id"), str)
            or not isinstance(source.get("page_number"), int)
            or source["page_number"] < 1
            for source in sources
        ):
            raise ValueError(f"In-scope case {case.get('id')} has an invalid relevant_sources entry.")
        if case.get("review_status") != "reviewed":
            raise ValueError(f"Dataset case {case.get('id')} has not been human-reviewed.")
        if case["in_scope"] and not case.get("knowledge_base_id"):
            raise ValueError(f"In-scope case {case.get('id')} needs a knowledge_base_id.")
    in_scope_count = sum(case["in_scope"] for case in cases)
    out_of_scope_count = len(cases) - in_scope_count
    if not 40 <= in_scope_count <= 50 or out_of_scope_count != 10:
        raise ValueError(
            f"Expected 40-50 in-scope and exactly 10 out-of-scope cases; got "
            f"{in_scope_count} and {out_of_scope_count}."
        )
    return cases


def load_chunks(knowledge_base_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.status == "indexed",
            )
        ).all()
    return [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "page_number": chunk.page_number,
            "document_id": document.id,
            "document_name": document.file_name,
        }
        for chunk, document in rows
    ]


class Retriever:
    def __init__(self, reranker_name: str):
        self.reranker_name = reranker_name
        self.chunks: dict[str, list[dict]] = {}
        self.bm25: dict[str, tuple[BM25Okapi, list[str]]] = {}
        self.vector_indexes: dict[str, tuple[faiss.Index, list[str]]] = {}

    def _corpus(self, kb_id: str) -> list[dict]:
        if kb_id not in self.chunks:
            self.chunks[kb_id] = load_chunks(kb_id)
            if not self.chunks[kb_id]:
                raise ValueError(f"No indexed chunks found for knowledge base {kb_id}.")
        return self.chunks[kb_id]

    def _keyword_index(self, kb_id: str, chunks: list[dict]):
        if kb_id not in self.bm25:
            self.bm25[kb_id] = (
                BM25Okapi([_tokenize(item["content"]) for item in chunks]),
                [item["chunk_id"] for item in chunks],
            )
        return self.bm25[kb_id]

    def _vector_index(self, kb_id: str):
        if kb_id not in self.vector_indexes:
            settings = get_settings()
            path = settings.faiss_dir / indexing._key(kb_id)
            index_file = path / "index.faiss"
            ids_file = path / "ids.json"
            if not index_file.exists() or not ids_file.exists():
                raise FileNotFoundError(
                    f"FAISS index is missing for knowledge base {kb_id}; index it before evaluation."
                )
            self.vector_indexes[kb_id] = (
                faiss.read_index(str(index_file)),
                json.loads(ids_file.read_text(encoding="utf-8")),
            )
        return self.vector_indexes[kb_id]

    async def retrieve(self, kb_id: str, question: str, config: str) -> list[dict]:
        chunks = self._corpus(kb_id)
        by_id = {item["chunk_id"]: item for item in chunks}
        limit = max(1, int(get_settings().top_k_candidates))
        candidate_limit = min(limit, len(chunks))

        keyword_model, keyword_ids = self._keyword_index(kb_id, chunks)
        keyword_scores = keyword_model.get_scores(_tokenize(question))
        keyword_positions = np.argsort(-keyword_scores, kind="stable")[:candidate_limit]
        keyword_rows = []
        for rank, position in enumerate(keyword_positions, start=1):
            score = float(keyword_scores[int(position)])
            if score > 0:
                chunk_id = keyword_ids[int(position)]
                row = dict(by_id[chunk_id])
                row.update(keyword_rank=rank, keyword_score=score)
                keyword_rows.append(row)

        if config == "BM25 only":
            return keyword_rows[:5]

        vector_index, vector_ids = self._vector_index(kb_id)
        query = await indexing.embed_texts([question])
        vector_scores, vector_positions = vector_index.search(
            query, min(candidate_limit, vector_index.ntotal)
        )
        vector_rows = []
        for rank, (score, position) in enumerate(
            zip(vector_scores[0], vector_positions[0]), start=1
        ):
            if 0 <= position < len(vector_ids):
                chunk_id = vector_ids[int(position)]
                row = dict(by_id[chunk_id])
                row.update(semantic_rank=rank, semantic_score=float(score))
                vector_rows.append(row)

        if config == "Vector only":
            return vector_rows[:5]

        sem_rank = {row["chunk_id"]: row["semantic_rank"] for row in vector_rows}
        kw_rank = {row["chunk_id"]: row["keyword_rank"] for row in keyword_rows}
        sem_score = {row["chunk_id"]: row["semantic_score"] for row in vector_rows}
        kw_score = {row["chunk_id"]: row["keyword_score"] for row in keyword_rows}
        ids = set(sem_rank) | set(kw_rank)
        sem_max = max(sem_score.values(), default=0.0)
        kw_max = max(kw_score.values(), default=0.0)
        settings = get_settings()
        sem_weight = float(settings.semantic_weight)
        kw_weight = float(settings.keyword_weight)
        weight_total = sem_weight + kw_weight or 1.0

        fused = []
        for chunk_id in ids:
            row = dict(by_id[chunk_id])
            row["semantic_rank"] = sem_rank.get(chunk_id)
            row["semantic_score"] = sem_score.get(chunk_id)
            row["keyword_rank"] = kw_rank.get(chunk_id)
            row["keyword_score"] = kw_score.get(chunk_id)
            if config == "Hybrid weighted":
                sem_norm = sem_score.get(chunk_id, 0.0) / sem_max if sem_max else 0.0
                kw_norm = kw_score.get(chunk_id, 0.0) / kw_max if kw_max else 0.0
                row["score"] = (
                    sem_weight * sem_norm + kw_weight * kw_norm
                ) / weight_total
            else:
                rrf_k = int(settings.rrf_k)
                row["rrf_score"] = (
                    sem_weight / weight_total / (rrf_k + sem_rank[chunk_id])
                    if chunk_id in sem_rank
                    else 0.0
                ) + (
                    kw_weight / weight_total / (rrf_k + kw_rank[chunk_id])
                    if chunk_id in kw_rank
                    else 0.0
                )
                row["score"] = row["rrf_score"]
            fused.append(row)

        score_field = "rrf_score" if config == "Hybrid RRF + reranker" else "score"
        fused.sort(key=lambda row: (-row[score_field], row["chunk_id"]))
        fused = fused[:candidate_limit]
        for rank, row in enumerate(fused, start=1):
            row["rrf_rank"] = rank
        if config == "Hybrid RRF + reranker" and self.reranker_name != "none":
            reranked = await get_reranker(self.reranker_name).rerank(
                question,
                fused,
            )
            if fused and not any("rerank_score" in item for item in reranked):
                raise RuntimeError(
                    f"The {self.reranker_name} reranker fell back to RRF order; "
                    "cannot report this run as reranked."
                )
            fused = reranked
        else:
            for rank, row in enumerate(fused, start=1):
                row["rerank_rank"] = rank
        return fused[:5]


def _relevant_sources(case: dict) -> set[tuple[str, int]]:
    return {
        (str(source["document_id"]), int(source["page_number"]))
        for source in case.get("relevant_sources", [])
    }


def _context(chunks: list[dict]) -> list[str]:
    return [
        f"{chunk['document_name']} page {chunk['page_number']}: {chunk['content']}"
        for chunk in chunks
    ]


def _approx_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


async def run(args: argparse.Namespace) -> None:
    cases = load_dataset(args.dataset)
    if args.reranker == "bge_local":
        try:
            import sentence_transformers  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "bge_local evaluation requires sentence-transformers; install the optional local reranker dependency."
            ) from exc
    elif args.reranker == "cohere":
        if not get_settings().cohere_api_key:
            raise RuntimeError("Set COHERE_API_KEY to evaluate the Cohere reranker.")
        try:
            import cohere  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Cohere evaluation requires the cohere package; install it before running."
            ) from exc
    in_scope = [case for case in cases if case["in_scope"]]
    if not in_scope:
        raise ValueError("Evaluation dataset needs at least one in-scope case.")
    oos_kb = args.out_of_scope_kb or in_scope[0].get("knowledge_base_id")
    if any(not case.get("knowledge_base_id") for case in in_scope):
        raise ValueError("Every in-scope case needs a knowledge_base_id.")
    if any(not case.get("knowledge_base_id") and not oos_kb for case in cases if not case["in_scope"]):
        raise ValueError(
            "Set --out-of-scope-kb so out-of-scope questions can be searched against your corpus."
        )

    retriever = Retriever(args.reranker)
    results = {
        config: {
            "retrieval": [],
            "generation": [],
            "times_ms": [],
            "input_tokens": [],
            "output_tokens": [],
            "refusals": [],
        }
        for config in CONFIG_NAMES
    }

    for case in cases:
        kb_id = case.get("knowledge_base_id") or oos_kb
        assert isinstance(kb_id, str)
        for config in CONFIG_NAMES:
            started = time.perf_counter()
            retrieved = await retriever.retrieve(kb_id, case["question"], config)
            retrieval_ms = (time.perf_counter() - started) * 1000
            metrics = retrieval_metrics(
                retrieved,
                _relevant_sources(case) if case["in_scope"] else set(),
                k=5,
            )
            if case["in_scope"]:
                results[config]["retrieval"].append(metrics)
            results[config]["times_ms"].append(retrieval_ms)

            if not args.generation:
                continue
            started = time.perf_counter()
            answer, _ = await generate_grounded_answer(
                case["question"],
                retrieved,
                [],
            )
            generation_ms = (time.perf_counter() - started) * 1000
            prompt_text = case["question"] + "\n" + "\n".join(_context(retrieved))
            results[config]["times_ms"][-1] += generation_ms
            results[config]["input_tokens"].append(_approx_tokens(prompt_text))
            results[config]["output_tokens"].append(_approx_tokens(answer))
            if not case["in_scope"]:
                results[config]["refusals"].append(is_correct_refusal(answer))
            results[config]["generation"].append(
                {
                    "question": case["question"],
                    "answer": answer,
                    "contexts": _context(retrieved),
                    "ground_truth": case.get("expected_answer", ""),
                    "in_scope": case["in_scope"],
                }
            )

    ragas_results = {}
    if args.generation:
        ragas_results = await run_ragas(results)
    report = make_report(results, cases, args, ragas_results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    chart_path = args.output.with_suffix(".svg")
    chart_path.write_text(make_chart(results), encoding="utf-8")
    print(f"Evaluation report: {args.output}")
    print(f"Chart: {chart_path}")


async def run_ragas(results: dict) -> dict:
    try:
        from datasets import Dataset
        from langchain_groq import ChatGroq
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except ImportError as exc:
        raise RuntimeError(
            "Generation evaluation requires optional dependencies. Install "
            "`pip install -r requirements-eval.txt`."
        ) from exc

    settings = get_settings()
    if settings.llm_provider != "groq" or not settings.groq_api_key:
        raise RuntimeError("RAGAS generation evaluation requires configured Groq credentials.")
    judge = LangchainLLMWrapper(
        ChatGroq(model=settings.llama_model, api_key=settings.groq_api_key, temperature=0)
    )
    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        embedding_backend = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
    else:
        try:
            from fastembed import TextEmbedding
            from langchain_core.embeddings import Embeddings
        except ImportError as exc:
            raise RuntimeError(
                "RAGAS answer relevancy needs embeddings. Configure OPENAI_API_KEY "
                "or install fastembed with `pip install -r requirements-eval.txt`."
            ) from exc

        class FastEmbedAdapter(Embeddings):
            def __init__(self):
                self.model = TextEmbedding()

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [vector.tolist() for vector in self.model.embed(texts)]

            def embed_query(self, text: str) -> list[float]:
                return next(self.model.embed([text])).tolist()

        embedding_backend = FastEmbedAdapter()

    embeddings = LangchainEmbeddingsWrapper(embedding_backend)
    scores = {}
    for config, values in results.items():
        rows = [row for row in values["generation"] if row["in_scope"]]
        if not rows:
            continue
        dataset = Dataset.from_list(
            [
                {key: row[key] for key in ("question", "answer", "contexts", "ground_truth")}
                for row in rows
            ]
        )
        evaluated = await asyncio.to_thread(
            lambda: evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision],
                llm=judge,
                embeddings=embeddings,
                raise_exceptions=False,
            )
        )
        frame = evaluated.to_pandas()
        scores[config] = {
            name: float(frame[name].mean())
            for name in ("faithfulness", "answer_relevancy", "context_precision")
            if name in frame.columns
        }
    return scores


def _mean(items: list[float], key: str) -> float:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    return sum(values) / len(values) if values else 0.0


def _format_score(value: object) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{score:.3f}" if math.isfinite(score) else "—"


def make_report(results: dict, cases: list[dict], args: argparse.Namespace, ragas_results: dict) -> str:
    rows = [
        "# RAG evaluation results",
        "",
        f"Cases: {len(cases)} ({sum(case['in_scope'] for case in cases)} in-scope, "
        f"{sum(not case['in_scope'] for case in cases)} out-of-scope)",
        f"Reranker: `{args.reranker}` · Generation enabled: `{args.generation}`",
        "",
        "| Configuration | Recall@5 | MRR | nDCG@5 | Page hit | Mean latency (ms) | Correct refusal | Tokens/question | RAGAS faithfulness | RAGAS answer relevance | RAGAS context precision | Est. LLM cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for config, values in results.items():
        retrieval = values["retrieval"]
        refusal_rate = (
            sum(values["refusals"]) / len(values["refusals"])
            if values["refusals"]
            else 0.0
        )
        input_tokens = sum(values["input_tokens"])
        output_tokens = sum(values["output_tokens"])
        token_mean = (
            (input_tokens + output_tokens) / len(values["generation"])
            if values["generation"]
            else 0.0
        )
        estimated_cost = (
            (
                input_tokens * (args.input_cost_per_million or 0)
                + output_tokens * (args.output_cost_per_million or 0)
            )
            / 1_000_000
            if args.input_cost_per_million is not None
            or args.output_cost_per_million is not None
            else None
        )
        ragas = ragas_results.get(config, {})
        row = [
            config,
            f"{_mean(retrieval, 'recall_at_5'):.3f}",
            f"{_mean(retrieval, 'mrr'):.3f}",
            f"{_mean(retrieval, 'ndcg_at_5'):.3f}",
            f"{_mean(retrieval, 'page_hit_rate'):.3f}",
            f"{sum(values['times_ms']) / len(values['times_ms']):.1f}" if values["times_ms"] else "0",
            f"{refusal_rate:.3f}" if values["refusals"] else "—",
            f"{token_mean:.0f}" if values["generation"] else "—",
            _format_score(ragas.get("faithfulness")) if ragas else "—",
            _format_score(ragas.get("answer_relevancy")) if ragas else "—",
            _format_score(ragas.get("context_precision")) if ragas else "—",
            f"${estimated_cost:.4f}"
            if values["generation"] and estimated_cost is not None
            else "—",
        ]
        rows.append("| " + " | ".join(row) + " |")

    if args.generation:
        rows.extend(
            [
                "",
                "Token counts are rough estimates at approximately 4 characters per token. "
                "Estimated spend uses the rates supplied on the command line and excludes RAGAS judge calls.",
                "",
                (
                    f"Rates: input ${args.input_cost_per_million or 0:.4f}/1M tokens; "
                    f"output ${args.output_cost_per_million or 0:.4f}/1M tokens."
                    if args.input_cost_per_million is not None
                    or args.output_cost_per_million is not None
                    else "Token pricing was not configured; estimated dollar costs are omitted."
                ),
            ]
        )
    rows.append("")
    return "\n".join(rows)


def make_chart(results: dict) -> str:
    width, height = 850, 290
    labels = list(results)
    bar_width = 450
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="28" font-family="Arial" font-size="16" font-weight="bold">Retrieval metrics (higher is better)</text>',
    ]
    colors = {"recall_at_5": "#5b65c9", "mrr": "#69a88b", "ndcg_at_5": "#e5a568"}
    for index, config in enumerate(labels):
        y = 62 + index * 54
        values = results[config]["retrieval"]
        elements.append(
            f'<text x="24" y="{y + 12}" font-family="Arial" font-size="11">{config}</text>'
        )
        x = 235
        for key, label in (
            ("recall_at_5", "Recall@5"),
            ("mrr", "MRR"),
            ("ndcg_at_5", "nDCG@5"),
        ):
            value = _mean(values, key)
            element_width = bar_width * max(0.0, min(value, 1.0)) / 3
            elements.append(
                f'<rect x="{x}" y="{y}" width="{element_width:.1f}" height="12" rx="3" fill="{colors[key]}"/>'
            )
            elements.append(
                f'<text x="{x + element_width + 5:.1f}" y="{y + 10}" font-family="Arial" font-size="9">{label} {value:.2f}</text>'
            )
            x += 175
    elements.append("</svg>")
    return "\n".join(elements)


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Compare vector, BM25, weighted hybrid, and RRF+reranker retrieval."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("eval/results.md"))
    parser.add_argument("--generation", action="store_true", help="Generate answers and run RAGAS (adds LLM/API cost).")
    parser.add_argument("--out-of-scope-kb")
    parser.add_argument("--reranker", choices=("none", "bge_local", "cohere"), default=settings.reranker)
    parser.add_argument("--input-cost-per-million", type=float)
    parser.add_argument("--output-cost-per-million", type=float)
    args = parser.parse_args()
    supplied_rates = [
        rate
        for rate in (args.input_cost_per_million, args.output_cost_per_million)
        if rate is not None
    ]
    if any(not math.isfinite(rate) or rate < 0 for rate in supplied_rates):
        parser.error("Token rates must be non-negative.")
    if args.generation and args.reranker == "none":
        logger.warning("The RRF configuration will have no reranking enabled.")
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
