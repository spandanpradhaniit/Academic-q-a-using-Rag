from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import Document
from app.services.storage import store_document, verify_s3_document


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy existing local PDF uploads to configured S3 storage."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to confirm external storage writes.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if not args.confirm:
        parser.error("Pass --confirm after verifying S3_BUCKET and credentials.")
    if settings.storage_backend.lower() != "s3":
        parser.error("Set STORAGE_BACKEND=s3 before migrating.")

    migrated = 0
    skipped = 0
    with SessionLocal() as db:
        documents = db.scalars(select(Document).order_by(Document.created_at)).all()
        for document in documents:
            current_path = Path(document.file_path)
            if not current_path.is_file():
                skipped += 1
                continue
            content = current_path.read_bytes()
            expected_sha256 = hashlib.sha256(content).hexdigest()
            if document.file_hash and expected_sha256 != document.file_hash:
                raise RuntimeError(
                    f"Local checksum mismatch for document {document.id}; refusing migration."
                )
            object_key = store_document(
                document.user_id,
                document.id,
                content,
            )
            verify_s3_document(object_key, expected_sha256)
            document.file_path = object_key
            db.commit()
            migrated += 1

    print(f"Migrated {migrated} PDFs to S3; skipped {skipped} missing/non-local files.")


if __name__ == "__main__":
    main()
