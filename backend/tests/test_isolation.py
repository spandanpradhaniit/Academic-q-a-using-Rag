from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import main
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import Document, KnowledgeBase


def _register(client: TestClient, name: str, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secure-passphrase"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_users_cannot_access_each_others_documents_or_conversations(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    async def _fake_answer(*args, **kwargs):
        return ("Course material contains syllabus.", "test-model")
    monkeypatch.setattr("app.api.routes.chat.generate_grounded_answer", _fake_answer)
    get_settings.cache_clear()
    owner_token = None
    with TestClient(main.app) as client:
        owner_token = _register(client, "Owner", "owner@example.edu")
        other_token = _register(client, "Other", "other@example.edu")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}

        override = main.app.dependency_overrides[get_db]
        db_generator = override()
        db = next(db_generator)
        try:
            owner_id = client.get("/api/auth/me", headers=owner_headers).json()["user_id"]
            knowledge_base_id = str(uuid4())
            document_id = str(uuid4())
            pdf_path = tmp_path / "private.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 private document")
            db.add(
                KnowledgeBase(
                    id=knowledge_base_id,
                    user_id=owner_id,
                    subject_id=None,
                    name="Private",
                )
            )
            db.add(
                Document(
                    id=document_id,
                    user_id=owner_id,
                    knowledge_base_id=knowledge_base_id,
                    title="Private document",
                    file_name="private.pdf",
                    file_path=str(pdf_path),
                    file_size=pdf_path.stat().st_size,
                    file_type="application/pdf",
                    file_hash="a" * 64,
                    status="indexed",
                )
            )
            db.commit()
        finally:
            db_generator.close()

        assert client.get("/api/documents", headers=other_headers).json() == []
        assert client.get(f"/api/documents/{document_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/documents/{document_id}/file", headers=other_headers).status_code == 404
        assert client.get(f"/api/documents/{document_id}/status", headers=other_headers).status_code == 404
        assert client.delete(f"/api/documents/{document_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/documents/{document_id}", headers=owner_headers).status_code == 200
        assert client.get(
            f"/api/documents/{document_id}/file", headers=owner_headers
        ).content == b"%PDF-1.4 private document"

        created = client.post(
            "/api/chat/ask",
            headers=owner_headers,
            json={"question": "What is in my course material?"},
        )
        assert created.status_code == 200
        conversation_id = created.json()["conversation_id"]
        denied = client.post(
            "/api/chat/ask",
            headers=other_headers,
            json={
                "question": "Continue this conversation",
                "conversation_id": conversation_id,
            },
        )
        assert denied.status_code == 404

        db_generator = override()
        db = next(db_generator)
        try:
            assert db.scalar(select(Document).where(Document.id == document_id)) is not None
        finally:
            db_generator.close()
    get_settings.cache_clear()
