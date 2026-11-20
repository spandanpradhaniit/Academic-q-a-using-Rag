from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import Document, DocumentChunk, KnowledgeBase, User
from app.api.routes.chat import NO_CONTEXT, _answer_history


def test_answer_history_omits_prior_no_context_responses():
    history = _answer_history(
        [
            SimpleNamespace(sender_type="user", content="about my IEEE conference paper"),
            SimpleNamespace(sender_type="assistant", content=NO_CONTEXT),
            SimpleNamespace(sender_type="assistant", content="A supported detail [Source 1]."),
        ]
    )

    assert history == [
        {"sender_type": "user", "content": "about my IEEE conference paper"},
        {"sender_type": "assistant", "content": "A supported detail [Source 1]."},
    ]


@pytest.mark.parametrize("has_context", [True, False])
def test_streamed_answer_uses_llm_with_or_without_retrieved_context(monkeypatch, has_context):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()
    generations = []
    streamed_messages = []

    class FakeLLM:
        async def astream(self, messages):
            generations.append("stream")
            streamed_messages.append(messages)
            answer = (
                "Supported answer [Source 1]."
                if has_context
                else "Here is a direct general answer."
            )
            yield SimpleNamespace(content=answer)

    async def fake_hybrid_search(*_args):
        return [
            {
                "chunk_id": "doc-1:0",
                "document_id": "doc-1",
                "document_name": "Course notes",
                "page_number": 2,
                "content": "Relevant source passage.",
                "score": 0.8,
            }
        ] if has_context else []

    async def no_follow_ups(*_args):
        return []

    monkeypatch.setattr(
        "app.api.routes.chat.hybrid_search",
        fake_hybrid_search,
    )
    monkeypatch.setattr(
        "app.api.routes.chat.relevance_gate",
        lambda candidates: candidates,
    )
    monkeypatch.setattr(
        "app.api.routes.chat.rewrite_question",
        lambda question, _history: f"{question} with retrieved context",
    )
    monkeypatch.setattr(
        "app.api.routes.chat.generate_grounded_answer",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("Streaming should not make a preliminary LLM call.")
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.chat.create_answer_model",
        lambda: (FakeLLM(), "test-model"),
    )
    monkeypatch.setattr(
        "app.api.routes.chat.generate_follow_up_questions",
        no_follow_ups,
    )

    with TestClient(main.app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "name": "Stream User",
                "email": "stream@example.edu",
                "password": "secure-passphrase",
            },
        )
        assert registered.status_code == 201
        user_id = registered.json()["user"]["user_id"]
        headers = {
            "Authorization": f"Bearer {registered.json()['access_token']}"
        }

        override = main.app.dependency_overrides[get_db]
        db_generator = override()
        db = next(db_generator)
        try:
            db.add(
                KnowledgeBase(
                    id="kb-stream",
                    user_id=user_id,
                    subject_id=None,
                    name="Stream KB",
                )
            )
            db.add(
                Document(
                    id="doc-1",
                    user_id=user_id,
                    knowledge_base_id="kb-stream",
                    title="Course notes",
                    file_name="notes.pdf",
                    file_path="/unused/notes.pdf",
                    file_size=1,
                    file_type="application/pdf",
                    file_hash="c" * 64,
                    status="indexed",
                )
            )
            db.add(
                DocumentChunk(
                    id="doc-1:0",
                    document_id="doc-1",
                    chunk_index=0,
                    content="Relevant source passage.",
                    page_number=2,
                    token_count=4,
                )
            )
            db.commit()
        finally:
            db_generator.close()

        response = client.post(
            "/api/chat/ask/stream",
            headers=headers,
            json={"question": "Explain the topic"},
        )
        assert response.status_code == 200
        assert '"type": "token"' in response.text
        assert '"type": "final"' in response.text
        expected_answer = (
            "Supported answer [Source 1]."
            if has_context
            else "Here is a direct general answer."
        )
        assert expected_answer in response.text
        assert generations == ["stream"]
        assert streamed_messages[0][-1].content == "Explain the topic with retrieved context"

    get_settings.cache_clear()
