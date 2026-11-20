# RAG evaluation

The evaluation set is test data, not training data. Generated question/answer pairs
must be checked against the cited PDF and corrected before reporting results. Do
not commit private course PDFs or answer keys.

## Build a dataset

From `backend/`, use the database user ID whose indexed documents you intend to
evaluate and supply ten out-of-scope questions:

```sh
python -m eval.dataset_builder \
  --user-id YOUR_USER_ID \
  --out-of-scope eval/out_of_scope.example.json \
  --in-scope-count 45 \
  --output eval/dataset.json
```

The builder samples indexed chunks deterministically (`--seed 17` by default)
and uses the configured LLM (Groq when `LLM_PROVIDER=groq`) to propose one
question and expected answer per chunk. Dataset generation makes model calls.
Review all 45 generated cases, including their source document/page, before use.
The output includes a `review_status` marker; change it to `reviewed` only after
verifying the case against the PDF.

Each in-scope case has this shape:

```json
{
  "id": "case-id",
  "question": "How does the paper define ...?",
  "expected_answer": "The paper defines ...",
  "knowledge_base_id": "knowledge-base-id",
  "in_scope": true,
  "relevant_sources": [
    {"document_id": "document-id", "page_number": 4}
  ],
  "review_status": "needs_human_review"
}
```

The out-of-scope example file is a starting point only; confirm these questions
are not answerable from the selected course library. Copy it and edit it for your
documents rather than relying on the generic examples.

## Run retrieval evaluation

Run from `backend/` after documents are indexed and the dataset is reviewed:

```sh
python -m eval.runner --dataset eval/dataset.json --out-of-scope-kb YOUR_KNOWLEDGE_BASE_ID
```

This compares vector-only, BM25-only, max-normalized weighted hybrid, and RRF
with the configured reranker. The report and an SVG chart are written to
`eval/results.md` and `eval/results.svg`. Retrieval metrics are deterministic
for a fixed index, configuration, and dataset (embedding backend determinism
still applies).

The runner expects in-scope cases to refer to the knowledge base containing
their source documents. The out-of-scope cases are run against
`--out-of-scope-kb` (or the first in-scope knowledge base if omitted), including
the retrieved passages when measuring refusal behavior.

## Optional generation and RAGAS

Install evaluation-only packages with `pip install -r requirements-eval.txt`,
then run:

```sh
python -m eval.runner \
  --dataset eval/dataset.json \
  --out-of-scope-kb YOUR_KNOWLEDGE_BASE_ID \
  --generation \
  --reranker bge_local \
  --input-cost-per-million INPUT_RATE \
  --output-cost-per-million OUTPUT_RATE
```

For the local BGE reranker, install `sentence-transformers` separately. For
Cohere, install `cohere` and set `COHERE_API_KEY`. Those packages/services are
optional and are checked explicitly before the corresponding benchmark runs.

Generation runs four answer passes per case and the RAGAS judge, so it makes
additional model calls and can incur charges. With Groq, answer generation and
the RAGAS LLM judge use the configured Groq model. RAGAS answer relevancy also
needs an embedding model: it uses `OPENAI_API_KEY` when configured or the local
FastEmbed model installed by `requirements-eval.txt`. Token counts are estimates;
the displayed cost uses only the
provided model-specific rates and excludes RAGAS judge calls. Reported latency
also excludes the separate RAGAS judge run.

Metrics: Recall@5, MRR, nDCG@5, page-level hit rate, mean latency, correct
out-of-scope refusal rate, estimated tokens/cost, and (when enabled) RAGAS
faithfulness, answer relevancy, and context precision.
