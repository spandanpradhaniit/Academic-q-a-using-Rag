from app.services.documents import process_document
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.workers.process_document",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def process_document_task(self, document_id: str, processing_job_id: str) -> None:
    process_document(document_id, processing_job_id)
