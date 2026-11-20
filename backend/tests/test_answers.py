import asyncio
import sys
from types import ModuleType, SimpleNamespace

from app.services import answers
from app.services.answers import validate_citations


def test_grounded_answer_prompt_requests_readable_numbered_qa(monkeypatch):
    captured = {}

    class FakeModel:
        async def ainvoke(self, messages):
            captured["system"] = messages[0].content
            return SimpleNamespace(
                content="1. **When does the internship start?**\n   It starts on August 1. [Source 1]"
            )

    monkeypatch.setattr(answers, "create_answer_model", lambda: (FakeModel(), "test-model"))

    answer, model = asyncio.run(
        answers.generate_grounded_answer(
            "List questions and answers from the offer letter.",
            [
                {
                    "document_name": "Offer letter",
                    "page_number": 1,
                    "content": "The internship starts on August 1.",
                }
            ],
            [],
        )
    )

    assert model == "test-model"
    assert "numbered list" in captured["system"]
    assert "numbered list (1., 2., 3.)" in captured["system"]
    assert "put supporting details under each item as bullet points" in captured["system"]
    assert "Avoid long passage-style prose" in captured["system"]
    assert "Never emit pipe-delimited pseudo-tables" in captured["system"]
    assert "use your general knowledge" in captured["system"]
    assert "[Source 1]" in answer


def test_answer_uses_model_when_retrieval_finds_no_passages(monkeypatch):
    captured = {}

    class FakeModel:
        async def ainvoke(self, messages):
            captured["system"] = messages[0].content
            return SimpleNamespace(content="Here are some useful questions about your request.")

    monkeypatch.setattr(answers, "create_answer_model", lambda: (FakeModel(), "groq-test-model"))

    answer, model = asyncio.run(
        answers.generate_grounded_answer("What questions can I ask?", [], [])
    )

    assert model == "groq-test-model"
    assert answer == "Here are some useful questions about your request."
    assert "use your general knowledge" in captured["system"]
    assert "=== SOURCE PASSAGES (UNTRUSTED DATA) ===\n\n===" in captured["system"]


def test_normalize_answer_markdown_repairs_inline_heading_separator():
    answer = answers.normalize_answer_markdown(
        "Intro text --- ## # 1. File name\nDetails follow."
    )

    assert answer == "Intro text\n\n## 1. File name\nDetails follow."


def test_validate_citations_keeps_valid_references():
    text = "This is supported by [Source 1] and [Source 3]."
    cleaned, invalid = validate_citations(text, 3)

    assert cleaned == text
    assert invalid == []


def test_validate_citations_normalizes_model_brackets():
    cleaned, invalid = validate_citations("Supported by 【Source 1】.", 1)

    assert cleaned == "Supported by [Source 1]."
    assert invalid == []


def test_validate_citations_removes_model_citations_without_sources():
    cleaned, invalid = validate_citations("General answer 【Source 1】.", 0)

    assert cleaned == "General answer ."
    assert invalid == []


def test_validate_citations_removes_invalid_sources():
    text = "The answer is in [Source 1], but the extra claim is in [Source 9]."
    cleaned, invalid = validate_citations(text, 2)

    assert cleaned == "The answer is in [Source 1], but the extra claim is in ."
    assert invalid == [9]


def test_follow_up_generation_parses_and_limits_json(monkeypatch):
    class FakeChat:
        def __init__(self, **_kwargs):
            pass

        async def ainvoke(self, _messages):
            return SimpleNamespace(content='["Question one?", "", "Question two?", 3, "Question three?", "Question four?"]')

    monkeypatch.setattr(
        answers,
        "get_settings",
        lambda: SimpleNamespace(
            llm_provider="openai",
            openai_api_key="test-key",
            openai_model="test-model",
        ),
    )
    fake_module = ModuleType("langchain_openai")
    fake_module.ChatOpenAI = FakeChat
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)

    result = asyncio.run(answers.generate_follow_up_questions("Question?", "Answer."))

    assert result == ["Question one?", "Question two?", "Question three?"]


def test_follow_up_generation_returns_empty_for_invalid_json(monkeypatch):
    class FakeChat:
        def __init__(self, **_kwargs):
            pass

        async def ainvoke(self, _messages):
            return SimpleNamespace(content="not-json")

    monkeypatch.setattr(
        answers,
        "get_settings",
        lambda: SimpleNamespace(
            llm_provider="openai",
            openai_api_key="test-key",
            openai_model="test-model",
        ),
    )
    fake_module = ModuleType("langchain_openai")
    fake_module.ChatOpenAI = FakeChat
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)

    assert asyncio.run(answers.generate_follow_up_questions("Question?", "Answer.")) == []
