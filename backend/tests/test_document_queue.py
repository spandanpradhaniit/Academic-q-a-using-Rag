from fastapi.testclient import TestClient

from app import main
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import ProcessingJob
from sqlalchemy import select


def test_upload_persists_job_and_dispatches_to_worker(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    dispatched = []

    def fake_enqueue(document_id, job_id, db):
        dispatched.append((document_id, job_id))

    monkeypatch.setattr(
        "app.api.routes.documents._enqueue_processing",
        fake_enqueue,
    )
    with TestClient(main.app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "name": "Student",
                "email": "queue-test@example.edu",
                "password": "secure-passphrase",
            },
        )
        assert registered.status_code == 201
        headers = {
            "Authorization": f"Bearer {registered.json()['access_token']}"
        }
        upload = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("course.pdf", b"%PDF-1.4 queue test", "application/pdf")},
        )
        assert upload.status_code == 202
        assert upload.json()["status"] == "Queued"
        document_id = upload.json()["document_id"]

        override = main.app.dependency_overrides[get_db]
        db_generator = override()
        db = next(db_generator)
        try:
            job = db.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.document_id == document_id
                )
            )
            assert job is not None
            assert job.status == "queued"
            assert job.id == dispatched[0][1]
        finally:
            db_generator.close()

    assert dispatched and dispatched[0][0] == document_id
    assert (tmp_path / registered.json()["user"]["user_id"] / f"{document_id}.pdf").is_file()
    get_settings.cache_clear()
