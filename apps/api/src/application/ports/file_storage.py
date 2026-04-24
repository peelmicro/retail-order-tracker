"""Port for blob storage. Infrastructure owns MinIO (dev) or AWS S3 (prod)."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class FileStorage(Protocol):
    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        """Store bytes under the given key. Returns the key for chaining."""
        ...

    def download(self, key: str) -> bytes:
        """Retrieve the bytes stored at the key."""
        ...

    def presigned_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        """Time-limited URL the frontend can use to fetch the object directly."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object. No-op if the key doesn't exist."""
        ...
