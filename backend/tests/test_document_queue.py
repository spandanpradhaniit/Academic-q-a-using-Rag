from fastapi.testclient import TestClient

from app import main
from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import ProcessingJob
from sqlalchemy import select


def test_upload_processes_inline_when_broker_is_not_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "celery_broker_url", "")
    processed = []

    def fake_process(document_id, job_id):
        processed.append((document_id, job_id))

    monkeypatch.setattr(
        "app.services.documents.process_document",
        fake_process,
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
        assert len(processed) == 1
        assert processed[0][0] == document_id
        retry = client.post(
            f"/api/documents/{document_id}/reprocess",
            headers=headers,
        )
        assert retry.status_code == 202
        assert len(processed) == 2
        assert processed[1][0] == document_id
        assert processed[1][1] != processed[0][1]

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
            assert job.id == processed[0][1]
        finally:
            db_generator.close()

    assert (tmp_path / registered.json()["user"]["user_id"] / f"{document_id}.pdf").is_file()
    get_settings.cache_clear()


def test_upload_dispatches_to_worker_when_broker_is_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "celery_broker_url", "redis://broker:6379/0")
    dispatched = []
    monkeypatch.setattr(
        "app.workers.tasks.process_document_task.delay",
        lambda document_id, job_id: dispatched.append((document_id, job_id)),
    )

    with TestClient(main.app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "name": "Student",
                "email": "queue-worker-test@example.edu",
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
    assert len(dispatched) == 1
    assert dispatched[0][0] == upload.json()["document_id"]
    get_settings.cache_clear()
