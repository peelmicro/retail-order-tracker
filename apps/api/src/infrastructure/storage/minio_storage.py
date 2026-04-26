"""MinIO adapter for the FileStorage port."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from src.config import settings


class MinioFileStorage:
    """FileStorage adapter backed by the MinIO Python client.

    Works unchanged against AWS S3, Google Cloud Storage, or Azure Blob (via
    their S3-compatible gateways) — only the endpoint + credentials change.
    """

    def __init__(
        self,
        client: Minio,
        bucket: str,
        presign_client: Minio | None = None,
    ) -> None:
        self._client = client
        self._bucket = bucket
        # Presigned URLs are signed against the client's endpoint hostname.
        # In Docker Compose the API talks to MinIO at `minio:9000` (internal
        # DNS), but the browser can only resolve `localhost:9000`. Use a
        # separate client configured with the public endpoint when one is
        # provided; otherwise fall back to the ops client.
        self._presign_client = presign_client or client

    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )
        return key

    def download(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def presigned_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return self._presign_client.presigned_get_object(
            self._bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    def delete(self, key: str) -> None:
        # MinIO's remove_object is a no-op if the key doesn't exist, but it
        # raises S3Error for other failures (e.g. bucket missing). Swallow
        # NoSuchKey to match the idempotent contract on the port.
        try:
            self._client.remove_object(self._bucket, key)
        except S3Error as exc:
            if exc.code != "NoSuchKey":
                raise


def make_minio_storage() -> MinioFileStorage:
    """Factory that builds a MinioFileStorage from the app settings.

    Two clients when a public endpoint is configured: one for ops
    (upload/download via the internal Docker DNS name) and one for
    presigning (with the host-resolvable hostname baked into the URL).

    `region="us-east-1"` is set explicitly because the public endpoint
    (`localhost:9000`) is NOT reachable from inside the API container —
    the Python minio client otherwise probes the endpoint to discover
    the bucket region the first time it presigns.
    """
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
        region="us-east-1",
    )
    presign_client: Minio | None = None
    public_endpoint = settings.minio_public_endpoint.strip()
    if public_endpoint and public_endpoint != settings.minio_endpoint:
        presign_client = Minio(
            public_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
            region="us-east-1",
        )
    return MinioFileStorage(client, settings.minio_bucket, presign_client=presign_client)


@lru_cache(maxsize=1)
def _storage_singleton() -> MinioFileStorage:
    return make_minio_storage()


def get_file_storage() -> MinioFileStorage:
    """FastAPI-style DI getter. Returns the memoised singleton."""
    return _storage_singleton()
