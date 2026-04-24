"""Shared test fakes."""


class InMemoryFileStorage:
    """FileStorage implementation backed by an in-memory dict.

    Round-trip-tested by tests/storage/test_minio_storage.py against the
    real adapter; this fake exists so use case tests don't need MinIO.
    """

    def __init__(self) -> None:
        self.store: dict[str, tuple[bytes, str | None]] = {}

    def upload(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.store[key] = (data, content_type)
        return key

    def download(self, key: str) -> bytes:
        return self.store[key][0]

    def presigned_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return f"http://test/{key}?expires={expires_seconds}"

    def delete(self, key: str) -> None:
        self.store.pop(key, None)
