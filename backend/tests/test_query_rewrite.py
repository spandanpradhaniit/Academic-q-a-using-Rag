import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.rag import query_rewrite
from app.rag.query_rewrite import rewrite_question


@pytest.mark.parametrize(
    "question, history, expected_terms",
    [
        ("what is normalization in DBMS?", [], ["normalization", "dbms"]),
        ("what are its advantages?", [{"sender_type": "user", "content": "what is normalization in DBMS?"}], ["normalization", "advantages"]),
        ("explain that more", [{"sender_type": "user", "content": "what is normalization in DBMS?"}], ["normalization", "more"]),
        ("what about the trade-offs?", [{"sender_type": "user", "content": "what is normalization in DBMS?"}], ["normalization", "trade-offs"]),
        ("can you compare it with denormalization?", [{"sender_type": "user", "content": "what is normalization in DBMS?"}], ["normalization", "denormalization"]),
        ("summarize this", [{"sender_type": "user", "content": "what is B-tree indexing?"}], ["b-tree", "indexing"]),
        ("what are the benefits of this approach?", [{"sender_type": "user", "content": "what is B-tree indexing?"}], ["b-tree", "benefits"]),
        ("how does it work?", [{"sender_type": "user", "content": "what is a hash join?"}], ["hash", "join", "work"]),
        ("why is that useful?", [{"sender_type": "user", "content": "what is a hash join?"}], ["hash", "join", "useful"]),
        ("list the advantages of this method", [{"sender_type": "user", "content": "what is a hash join?"}], ["hash", "join", "advantages"]),
    ],
)
def test_rewrite_question_handles_followups(question, history, expected_terms):
    result = rewrite_question(question, history)
    lowered = result.lower()
    for term in expected_terms:
        assert term.lower() in lowered


def test_rewrite_question_returns_original_when_no_history():
    assert rewrite_question("what is normalization in DBMS?", []) == "what is normalization in DBMS?"


def test_rewrite_question_returns_original_when_already_standalone():
    history = [{"sender_type": "user", "content": "what is normalization in DBMS?"}]
    question = "what is normalization in DBMS?"
    assert rewrite_question(question, history) == question


def test_rewrite_question_uses_last_standalone_topic_after_repeated_followup():
    history = [
        {"sender_type": "user", "content": "about my IEEE conference paper"},
        {"sender_type": "assistant", "content": "Information not found in the provided documents."},
        {"sender_type": "user", "content": "Can you explain this in more detail?"},
        {"sender_type": "assistant", "content": "Information not found in the provided documents."},
    ]

    result = rewrite_question("Can you explain this in more detail?", history)

    assert "ieee conference paper" in result.lower()
    assert result.lower().count("can you explain this in more detail") == 1


def test_groq_query_rewrite_uses_groq_answer_model(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="groq",
        llama_model="openai/gpt-oss-120b",
        rewrite_model="gpt-4o-mini",
        rewrite_timeout_seconds=2,
        groq_api_key="test-key",
        openai_api_key="",
    )
    monkeypatch.setattr(query_rewrite, "get_settings", lambda: settings)
    requested_models = []

    class FakeChatGroq:
        def __init__(self, **kwargs):
            requested_models.append(kwargs["model"])

        async def ainvoke(self, messages):
            return SimpleNamespace(content="Explain the IEEE conference paper in more detail.")

    monkeypatch.setitem(
        sys.modules,
        "langchain_groq",
        SimpleNamespace(ChatGroq=FakeChatGroq),
    )

    result = asyncio.run(
        query_rewrite._rewrite_with_llm(
            "Can you explain this in more detail?",
            [{"sender_type": "user", "content": "about my IEEE conference paper"}],
        )
    )

    assert requested_models == ["openai/gpt-oss-120b"]
    assert "IEEE conference paper" in result
