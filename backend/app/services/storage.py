from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_settings


def _s3_client():
    settings = get_settings()
    if not settings.s3_bucket:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3.")
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("Install boto3 to use STORAGE_BACKEND=s3.") from exc

    credentials = {}
    if settings.s3_access_key_id:
        credentials["aws_access_key_id"] = settings.s3_access_key_id
    if settings.s3_secret_access_key:
        credentials["aws_secret_access_key"] = settings.s3_secret_access_key
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path"}),
        **credentials,
    )


def store_document(owner_id: str, document_id: str, content: bytes) -> str:
    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "s3":
        key = f"users/{owner_id}/documents/{document_id}.pdf"
        _s3_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType="application/pdf",
            Metadata={"sha256": hashlib.sha256(content).hexdigest()},
        )
        return key
    if backend != "local":
        raise RuntimeError(f"Unsupported STORAGE_BACKEND: {settings.storage_backend}")

    path = settings.upload_dir / owner_id / f"{document_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def materialize_document(storage_path: str, destination: Path) -> Path:
    settings = get_settings()
    if settings.storage_backend.lower() == "s3":
        try:
            _s3_client().download_file(settings.s3_bucket, storage_path, str(destination))
        except ClientError as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError(storage_path) from exc
            raise
        return destination

    path = Path(storage_path)
    if not path.is_file():
        raise FileNotFoundError(storage_path)
    return path


def document_response(storage_path: str, file_name: str):
    settings = get_settings()
    if settings.storage_backend.lower() != "s3":
        path = Path(storage_path)
        if not path.is_file():
            raise FileNotFoundError(storage_path)
        return FileResponse(path, media_type="application/pdf", filename=file_name)

    try:
        response = _s3_client().get_object(Bucket=settings.s3_bucket, Key=storage_path)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            raise FileNotFoundError(storage_path) from exc
        raise
    body = response["Body"]

    def stream():
        try:
            yield from body.iter_chunks(chunk_size=1024 * 1024)
        finally:
            body.close()

    return StreamingResponse(
        stream(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(file_name)}",
            "Content-Length": str(response["ContentLength"]),
        },
    )


def delete_document_file(storage_path: str) -> None:
    settings = get_settings()
    if settings.storage_backend.lower() == "s3":
        _s3_client().delete_object(Bucket=settings.s3_bucket, Key=storage_path)
        return
    Path(storage_path).unlink(missing_ok=True)


def verify_s3_document(storage_path: str, expected_sha256: str) -> None:
    settings = get_settings()
    response = _s3_client().head_object(
        Bucket=settings.s3_bucket,
        Key=storage_path,
    )
    actual_sha256 = response.get("Metadata", {}).get("sha256")
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"S3 checksum verification failed for {storage_path}.")
