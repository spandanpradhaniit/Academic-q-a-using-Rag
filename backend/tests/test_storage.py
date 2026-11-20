from pathlib import Path
from types import SimpleNamespace

from app.services import storage


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = {
            "body": kwargs["Body"],
            "metadata": kwargs["Metadata"],
        }

    def download_file(self, bucket, key, destination):
        Path(destination).write_bytes(self.objects[key]["body"])

    def head_object(self, **kwargs):
        return {"Metadata": self.objects[kwargs["Key"]]["metadata"]}

    def delete_object(self, **kwargs):
        del self.objects[kwargs["Key"]]


def test_local_storage_round_trip_and_delete(monkeypatch, tmp_path):
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: SimpleNamespace(storage_backend="local", upload_dir=tmp_path),
    )
    content = b"%PDF-1.4 local"

    object_path = storage.store_document("owner", "document", content)
    assert Path(object_path).read_bytes() == content
    assert storage.materialize_document(object_path, tmp_path / "unused") == Path(object_path)
    assert storage.document_response(object_path, "source.pdf").media_type == "application/pdf"

    storage.delete_document_file(object_path)
    assert not Path(object_path).exists()


def test_s3_storage_round_trip_and_checksum(monkeypatch, tmp_path):
    client = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: SimpleNamespace(
            storage_backend="s3",
            s3_bucket="private-documents",
        ),
    )
    content = b"%PDF-1.4 s3"
    object_key = storage.store_document("owner", "document", content)

    assert object_key == "users/owner/documents/document.pdf"
    downloaded = storage.materialize_document(object_key, tmp_path / "source.pdf")
    assert downloaded.read_bytes() == content
    storage.verify_s3_document(object_key, client.objects[object_key]["metadata"]["sha256"])

    storage.delete_document_file(object_key)
    assert object_key not in client.objects
