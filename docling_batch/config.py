"""Constants and environment-backed settings."""

from __future__ import annotations

import os

VERSION = "3.0.0"

DEFAULT_PILLOW = "9999999999"
DEFAULT_OCR_MAX_PIXELS = 50_000_000
DEFAULT_OCR_MAX_SIDE = 8192
OCR_MAX_SIDES = (8192, 4096, 2048)
MIN_OCR_SIDE = 32
MIN_OUTPUT_CHARS = 32
MIN_TILE_CHARS = 4
MAX_ATTEMPTS = 3
RETRY_DELAY_SEC = 5

SUPPORTED_EXT = frozenset({
    "pdf", "docx", "xlsx", "pptx",
    "md", "markdown", "adoc", "asciidoc", "tex",
    "html", "htm", "xhtml", "csv", "vtt",
    "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp",
    "wav", "mp3", "m4a", "aac", "ogg", "flac",
    "mp4", "avi", "mov", "json", "xml",
})

CONVERSION_FAILURE_MARKERS = (
    "DecompressionBombError",
    "ResizeImgError",
    "failed to convert",
    "is not valid",
    "Could not load image",
    "No module named docling",
    "cannot be directly executed",
)

OUTPUT_SUFFIXES = (".md", ".html", ".json", ".txt")


def pillow_limit() -> str:
    return (
        os.environ.get("DOCLING_PILLOW_MAX_PIXELS")
        or os.environ.get("PILLOW_MAX_IMAGE_PIXELS")
        or DEFAULT_PILLOW
    )


def ocr_max_pixels() -> int:
    raw = os.environ.get("DOCLING_OCR_MAX_PIXELS")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_OCR_MAX_PIXELS


def ocr_max_side_for_attempt(attempt: int) -> int:
    idx = min(attempt - 1, len(OCR_MAX_SIDES) - 1)
    raw = os.environ.get("DOCLING_OCR_MAX_SIDE")
    if raw and attempt == 1:
        try:
            return int(raw)
        except ValueError:
            pass
    return OCR_MAX_SIDES[idx]
