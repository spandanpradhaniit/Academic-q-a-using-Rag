import json
from argparse import Namespace

import pytest

from eval.metrics import is_correct_refusal, retrieval_metrics
from eval.runner import CONFIG_NAMES, load_dataset, make_chart, make_report


def test_retrieval_metrics_compute_rank_and_page_hits():
    ranked = [
        {"document_id": "doc-a", "page_number": 2},
        {"document_id": "doc-b", "page_number": 7},
        {"document_id": "doc-a", "page_number": 4},
    ]
    metrics = retrieval_metrics(ranked, {("doc-a", 4), ("doc-b", 7)})

    assert metrics["recall_at_5"] == 1
    assert metrics["mrr"] == 0.5
    assert metrics["page_hit_rate"] == 1
    assert 0 < metrics["ndcg_at_5"] <= 1


def test_retrieval_metrics_zero_for_no_matches():
    metrics = retrieval_metrics(
        [{"document_id": "doc-a", "page_number": 1}],
        {("doc-b", 2)},
    )

    assert metrics == {
        "recall_at_5": 0,
        "mrr": 0,
        "ndcg_at_5": 0,
        "page_hit_rate": 0,
    }


def test_correct_refusal_detection():
    assert is_correct_refusal("The documents do not contain enough information.")
    assert not is_correct_refusal("The documents explain the topic in detail.")


def test_load_dataset_requires_reviewed_40_plus_10_cases(tmp_path):
    cases = [
        {
            "id": f"in-{index}",
            "question": f"Question {index}?",
            "expected_answer": f"Expected answer {index}.",
            "knowledge_base_id": "kb-1",
            "in_scope": True,
            "relevant_sources": [{"document_id": "doc-1", "page_number": 1}],
            "review_status": "reviewed",
        }
        for index in range(40)
    ]
    cases.extend(
        {
            "id": f"out-{index}",
            "question": f"Out-of-scope question {index}?",
            "expected_answer": "",
            "knowledge_base_id": None,
            "in_scope": False,
            "relevant_sources": [],
            "review_status": "reviewed",
        }
        for index in range(10)
    )
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")

    assert len(load_dataset(path)) == 50


def test_load_dataset_rejects_unreviewed_cases(tmp_path):
    cases = [
        {
            "id": "in",
            "question": "Question?",
            "expected_answer": "Answer.",
            "knowledge_base_id": "kb-1",
            "in_scope": True,
            "relevant_sources": [{"document_id": "doc-1", "page_number": 1}],
            "review_status": "needs_human_review",
        }
    ] * 40
    cases.extend(
        {
            "id": f"out-{index}",
            "question": f"Out question {index}?",
            "expected_answer": "",
            "knowledge_base_id": None,
            "in_scope": False,
            "relevant_sources": [],
            "review_status": "reviewed",
        }
        for index in range(10)
    )
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")

    with pytest.raises(ValueError, match="human-reviewed"):
        load_dataset(path)


def test_report_outputs_markdown_table_and_svg_chart_without_fake_cost():
    results = {
        config: {
            "retrieval": [
                {
                    "recall_at_5": 0.8,
                    "mrr": 0.6,
                    "ndcg_at_5": 0.7,
                    "page_hit_rate": 1.0,
                }
            ],
            "generation": [],
            "times_ms": [125.0],
            "input_tokens": [],
            "output_tokens": [],
            "refusals": [],
        }
        for config in CONFIG_NAMES
    }
    args = Namespace(
        reranker="bge_local",
        generation=False,
        input_cost_per_million=None,
        output_cost_per_million=None,
    )
    cases = [
        {"in_scope": True},
        {"in_scope": False},
    ]

    report = make_report(results, cases, args, {})
    chart = make_chart(results)

    assert "| Configuration | Recall@5 |" in report
    assert "0.800" in report
    assert chart.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "RRF + reranker" in chart
