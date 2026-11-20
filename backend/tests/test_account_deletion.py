from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import main
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import (
    Conversation,
    Document,
    KnowledgeBase,
    Message,
    RefreshToken,
    SearchQuery,
    User,
)


def test_account_deletion_removes_files_indexes_and_owned_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "faiss_dir", tmp_path / "faiss")
    monkeypatch.setattr(settings, "bm25_dir", tmp_path / "bm25")

    with TestClient(main.app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "name": "Delete Me",
                "email": "delete-me@example.edu",
                "password": "secure-passphrase",
            },
        )
        assert registered.status_code == 201
        owner_id = registered.json()["user"]["user_id"]
        headers = {
            "Authorization": f"Bearer {registered.json()['access_token']}"
        }
        knowledge_base_id = str(uuid4())
        document_id = str(uuid4())
        conversation_id = str(uuid4())
        message_id = str(uuid4())
        source_file = tmp_path / "owned.pdf"
        source_file.write_bytes(b"%PDF-1.4 account deletion")
        faiss_dir = settings.faiss_dir / knowledge_base_id
        bm25_dir = settings.bm25_dir / knowledge_base_id
        faiss_dir.mkdir(parents=True)
        bm25_dir.mkdir(parents=True)
        (faiss_dir / "index.faiss").write_text("index")
        (bm25_dir / "corpus.json").write_text("[]")

        override = main.app.dependency_overrides[get_db]
        db_generator = override()
        db = next(db_generator)
        try:
            db.add(
                KnowledgeBase(
                    id=knowledge_base_id,
                    user_id=owner_id,
                    subject_id=None,
                    name="Owned",
                    vector_store="faiss",
                )
            )
            db.add(
                Document(
                    id=document_id,
                    user_id=owner_id,
                    knowledge_base_id=knowledge_base_id,
                    title="Owned PDF",
                    file_name="owned.pdf",
                    file_path=str(source_file),
                    file_size=source_file.stat().st_size,
                    file_type="application/pdf",
                    file_hash="b" * 64,
                    status="indexed",
                )
            )
            db.add(
                Conversation(
                    id=conversation_id,
                    user_id=owner_id,
                    title="Owned conversation",
                )
            )
            db.add(
                Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    sender_type="user",
                    content="private question",
                )
            )
            db.add(
                SearchQuery(
                    id=str(uuid4()),
                    user_id=owner_id,
                    conversation_id=conversation_id,
                    query_text="private question",
                )
            )
            db.commit()
        finally:
            db_generator.close()

        incorrect = client.request(
            "DELETE",
            "/api/auth/me",
            headers=headers,
            json={"password": "wrong-password"},
        )
        assert incorrect.status_code == 401
        assert source_file.exists()

        deleted = client.request(
            "DELETE",
            "/api/auth/me",
            headers=headers,
            json={"password": "secure-passphrase"},
        )
        assert deleted.status_code == 204
        assert not source_file.exists()
        assert not faiss_dir.exists()
        assert not bm25_dir.exists()
        assert client.get("/api/auth/me", headers=headers).status_code == 401

        db_generator = override()
        db = next(db_generator)
        try:
            assert db.get(User, owner_id) is None
            assert db.get(Document, document_id) is None
            assert db.get(KnowledgeBase, knowledge_base_id) is None
            assert db.scalar(
                select(RefreshToken).where(RefreshToken.user_id == owner_id)
            ) is None
            assert db.scalar(
                select(SearchQuery).where(SearchQuery.user_id == owner_id)
            ) is None
        finally:
            db_generator.close()
    get_settings.cache_clear()
