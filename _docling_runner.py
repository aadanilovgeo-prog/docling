#!/usr/bin/env python3
"""Run docling CLI with Pillow limit applied before PIL/docling import."""
from __future__ import annotations

import os
import sys


def _apply_pillow_limit() -> None:
    limit = (
        os.environ.get("DOCLING_PILLOW_MAX_PIXELS")
        or os.environ.get("PILLOW_MAX_IMAGE_PIXELS")
        or "9999999999"
    )
    os.environ["PILLOW_MAX_IMAGE_PIXELS"] = limit
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = int(limit)
    except (ImportError, ValueError, OverflowError):
        pass


def main() -> None:
    _apply_pillow_limit()
    sys.argv = ["docling", *sys.argv[1:]]
    from docling.cli.main import app as cli_app

    cli_app()


if __name__ == "__main__":
    main()
