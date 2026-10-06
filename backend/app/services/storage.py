"""Pluggable object storage for product images.

Two backends ship with V1:

* ``local`` — writes files under ``MEDIA_ROOT`` and serves them via the
  ``/media`` StaticFiles mount. Zero external dependencies; ideal for dev.
* ``s3``    — uploads to any S3-compatible bucket (AWS S3, MinIO, Cloudflare R2,
  DigitalOcean Spaces …) with ``boto3`` and returns a public/CDN URL.

Swap ``STORAGE_BACKEND`` in the environment to switch. The admin upload endpoint
(``POST /admin/uploads``) is the only caller.
"""
from __future__ import annotations

import mimetypes
import re
import secrets
from pathlib import Path
from typing import Protocol

from app.core.config import settings

# Only allow web-friendly image types; keeps the upload surface small.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


class StorageError(Exception):
    """Raised when an upload cannot be stored."""


class Storage(Protocol):
    name: str

    def save(self, data: bytes, content_type: str, original_name: str) -> str:
        """Persist ``data`` and return a public URL."""
        ...


def _safe_key(original_name: str, content_type: str) -> str:
    stem = Path(original_name or "image").stem
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-").lower() or "image"
    ext = ALLOWED_CONTENT_TYPES.get(content_type) or (
        mimetypes.guess_extension(content_type) or ".bin"
    )
    return f"products/{stem}-{secrets.token_hex(8)}{ext}"


class LocalStorage:
    name = "local"

    def save(self, data: bytes, content_type: str, original_name: str) -> str:
        key = _safe_key(original_name, content_type)
        dest = Path(settings.MEDIA_ROOT) / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        base = settings.PUBLIC_MEDIA_BASE_URL.rstrip("/")
        prefix = settings.MEDIA_URL_PREFIX.strip("/")
        return f"{base}/{prefix}/{key}"


class S3Storage:
    name = "s3"

    def __init__(self) -> None:
        import boto3  # imported lazily so dev/test need not install it

        self._client = boto3.client(
            "s3",
            region_name=settings.S3_REGION or None,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        )

    def save(self, data: bytes, content_type: str, original_name: str) -> str:
        key = _safe_key(original_name, content_type)
        try:
            self._client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as exc:  # boto3 raises ClientError / BotoCoreError
            raise StorageError(str(exc)) from exc

        if settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        if settings.S3_ENDPOINT_URL:
            return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET}/{key}"
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{key}"


def get_storage() -> Storage:
    if settings.STORAGE_BACKEND.lower() == "s3":
        return S3Storage()
    return LocalStorage()
