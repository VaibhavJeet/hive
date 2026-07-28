"""
Upload validation helpers (HIVE-011, HIVE-029).

Two problems these solve:

**The declared content type is not evidence.** `UploadFile.content_type` comes from the
client's multipart header. Trusting it lets a caller upload arbitrary bytes labelled
`image/png` — which then gets served back from our origin with that MIME type. We sniff
the leading bytes instead and require them to agree with the declaration.

**Reading before validating is a denial of service.** The size limit was checked with
`len(content)` *after* `await file.read()` had already pulled the whole body into
memory, so a multi-gigabyte upload exhausted RAM before the 10 MB limit was consulted.
`read_upload_within_limit` streams and aborts as soon as the cap is passed.
"""

from typing import Optional

# Magic-byte signatures for the formats in ALLOWED_IMAGE_TYPES / ALLOWED_VIDEO_TYPES.
# (offset, signature, mime). Kept explicit rather than pulling in python-magic, which
# needs a native library and is awkward to install on Windows.
_SIGNATURES = [
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"RIFF", "image/webp"),          # refined below — RIFF also covers .wav/.avi
    (4, b"ftyp", "video/mp4"),
    (0, b"\x1a\x45\xdf\xa3", "video/webm"),
]

# Declared types we accept as equivalent to a sniffed type. `.mov` and `.mp4` share the
# ISO base media container, so `ftyp` cannot tell them apart.
_EQUIVALENT = {
    "video/mp4": {"video/mp4", "video/quicktime"},
    "image/webp": {"image/webp"},
}

CHUNK_SIZE = 64 * 1024


def sniff_content_type(head: bytes) -> Optional[str]:
    """Identify a file from its leading bytes, or None if unrecognised."""
    for offset, signature, mime in _SIGNATURES:
        if head[offset:offset + len(signature)] == signature:
            if signature == b"RIFF":
                # RIFF is a container; only WEBP is in the allowlist.
                if head[8:12] != b"WEBP":
                    return None
            return mime
    return None


def content_type_matches(declared: str, sniffed: Optional[str]) -> bool:
    """Whether a sniffed type is consistent with what the client declared."""
    if sniffed is None:
        return False
    if declared == sniffed:
        return True
    return declared in _EQUIVALENT.get(sniffed, set())


class UploadTooLarge(Exception):
    """Raised as soon as an upload passes its size cap, before it is buffered."""

    def __init__(self, limit_bytes: int):
        self.limit_bytes = limit_bytes
        super().__init__(
            f"File exceeds the maximum allowed size of "
            f"{limit_bytes / (1024 * 1024):.1f} MB"
        )


async def read_upload_within_limit(file, limit_bytes: int) -> bytes:
    """Read an UploadFile, aborting once `limit_bytes` is exceeded.

    Streaming matters: the previous code read the entire body and *then* checked its
    length, so the size limit protected disk but not memory.
    """
    chunks = []
    total = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit_bytes:
            raise UploadTooLarge(limit_bytes)
        chunks.append(chunk)

    return b"".join(chunks)
