"""Pillow decompression limit helpers."""

from __future__ import annotations

import os

from docling_batch.config import DEFAULT_PILLOW, pillow_limit

# Set before any Pillow import in this process.
os.environ.setdefault("PILLOW_MAX_IMAGE_PIXELS", DEFAULT_PILLOW)


def apply_pillow_limit() -> None:
    val = pillow_limit()
    os.environ["PILLOW_MAX_IMAGE_PIXELS"] = val
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = int(val)
    except (ImportError, ValueError, OverflowError):
        pass
