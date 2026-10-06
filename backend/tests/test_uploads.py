"""Admin image upload endpoint (local storage backend)."""
from __future__ import annotations

from app.core.config import settings
from tests.conftest import auth

# A minimal valid 1x1 PNG.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


def test_admin_can_upload_image(client, admin_token, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    r = client.post(
        "/api/v1/admin/uploads",
        headers=auth(admin_token),
        files={"file": ("sofa.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert "/media/products/" in url and url.endswith(".png")
    # File was actually written to the storage root.
    written = list(tmp_path.rglob("*.png"))
    assert len(written) == 1 and written[0].read_bytes() == PNG_BYTES


def test_upload_rejects_non_image(client, admin_token):
    r = client.post(
        "/api/v1/admin/uploads",
        headers=auth(admin_token),
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_upload_rejects_empty_file(client, admin_token, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    r = client.post(
        "/api/v1/admin/uploads",
        headers=auth(admin_token),
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert r.status_code == 400


def test_upload_requires_admin(client, user_token):
    r = client.post(
        "/api/v1/admin/uploads",
        headers=auth(user_token),
        files={"file": ("sofa.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 403

    anon = client.post(
        "/api/v1/admin/uploads",
        files={"file": ("sofa.png", PNG_BYTES, "image/png")},
    )
    assert anon.status_code == 401
