"""
Media upload/serving hardening tests (HIVE-011, HIVE-028, HIVE-029).

Three defects in the same ~100 lines:

    HIVE-011  authenticated but unlimited — one account could fill the disk, or the
              object-storage bill, 10 MB at a time
    HIVE-028  `filename` is a path parameter joined straight onto the storage root,
              so percent-encoded traversal escaped the media directory
    HIVE-029  the declared Content-Type was trusted, and the size cap was applied
              with len(content) *after* the whole body was already in memory
"""

from pathlib import Path

import pytest

from mind.media.validation import (
    UploadTooLarge,
    content_type_matches,
    read_upload_within_limit,
    sniff_content_type,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 28
GIF = b"GIF89a" + b"\x00" * 26
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
MP4 = b"\x00\x00\x00\x20" + b"ftyp" + b"\x00" * 24
ELF = b"\x7fELF" + b"\x00" * 28


# ============================================================================
# HIVE-029 — the declared content type is not evidence
# ============================================================================

@pytest.mark.parametrize(
    "payload,expected",
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"),
     (WEBP, "image/webp"), (MP4, "video/mp4")],
)
def test_sniffing_identifies_allowed_formats(payload, expected):
    assert sniff_content_type(payload) == expected


def test_unknown_content_is_not_identified():
    assert sniff_content_type(ELF) is None
    assert sniff_content_type(b"") is None


def test_executable_labelled_as_png_is_rejected():
    """The attack: upload arbitrary bytes, have them served back as an image."""
    assert not content_type_matches("image/png", sniff_content_type(ELF))


def test_png_bytes_declared_as_png_are_accepted():
    assert content_type_matches("image/png", sniff_content_type(PNG))


def test_mov_and_mp4_share_a_container_and_are_treated_as_equivalent():
    """`ftyp` cannot distinguish them, so rejecting .mov would be a false positive."""
    assert content_type_matches("video/quicktime", sniff_content_type(MP4))


def test_riff_that_is_not_webp_is_rejected():
    """RIFF also covers .wav and .avi, neither of which is in the allowlist."""
    wav = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 20
    assert sniff_content_type(wav) is None


def test_mismatched_image_types_are_rejected():
    assert not content_type_matches("image/png", sniff_content_type(JPEG))


# ============================================================================
# HIVE-029 — size is enforced while streaming, not after buffering
# ============================================================================

class _FakeUpload:
    """Minimal UploadFile stand-in that yields a body in chunks."""

    def __init__(self, body: bytes):
        self._body = body
        self._pos = 0
        self.bytes_served = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._body[self._pos:]
        else:
            chunk = self._body[self._pos:self._pos + size]
        self._pos += len(chunk)
        self.bytes_served += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_upload_within_the_limit_is_returned_whole():
    upload = _FakeUpload(b"x" * 1000)
    assert await read_upload_within_limit(upload, 2000) == b"x" * 1000


@pytest.mark.asyncio
async def test_oversized_upload_raises():
    upload = _FakeUpload(b"x" * 5000)
    with pytest.raises(UploadTooLarge):
        await read_upload_within_limit(upload, 1000)


@pytest.mark.asyncio
async def test_oversized_upload_is_abandoned_early():
    """The point of streaming: we must not buffer a huge body to reject it."""
    limit = 1000
    upload = _FakeUpload(b"x" * (50 * 1024 * 1024))

    with pytest.raises(UploadTooLarge):
        await read_upload_within_limit(upload, limit)

    # One chunk past the limit is enough to decide; we must not have read it all.
    assert upload.bytes_served < 10 * limit + 65536, (
        f"read {upload.bytes_served} bytes to enforce a {limit}-byte limit"
    )


# ============================================================================
# HIVE-028 — path traversal on the file-serving endpoints
# ============================================================================

@pytest.fixture
def storage_root(tmp_path):
    root = tmp_path / "media"
    (root / "images").mkdir(parents=True)
    (root / "images" / "ok.png").write_bytes(PNG)
    (tmp_path / "secret.txt").write_text("password=hunter2")
    return root


def _resolve(root, *parts):
    from mind.api.routes.media import _resolve_within_storage

    return _resolve_within_storage(root, *parts)


def test_legitimate_file_resolves(storage_root):
    assert _resolve(storage_root, "images", "ok.png").exists()


@pytest.mark.parametrize(
    "filename",
    ["../secret.txt", "../../secret.txt", "..\\secret.txt", "subdir/../../secret.txt"],
)
def test_traversal_is_rejected(storage_root, filename):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _resolve(storage_root, "images", filename)
    assert exc.value.status_code == 400


def test_absolute_path_is_rejected(storage_root, tmp_path):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _resolve(storage_root, "images", str(tmp_path / "secret.txt"))


def test_decoded_traversal_is_rejected(storage_root):
    """Starlette decodes path params before the handler sees them, so %2e%2e%2f
    arrives here as `../` — the exact case that made this exploitable."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _resolve(storage_root, "images", "../" + "secret.txt")
