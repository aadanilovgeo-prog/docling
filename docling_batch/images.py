"""Image sizing, tiling, and OCR prep."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Literal

from docling_batch.config import MIN_OCR_SIDE, ocr_max_pixels
from docling_batch.io import log_append
from docling_batch.models import App, OcrPrepareResult, TilePlan
from docling_batch.pillow_util import apply_pillow_limit

Axis = Literal["vertical", "horizontal"]


def _png_size_fast(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return None
            while True:
                header = f.read(8)
                if len(header) < 8:
                    return None
                length, ctype = struct.unpack(">I4s", header)
                data = f.read(length)
                f.read(4)
                if ctype == b"IHDR" and len(data) >= 8:
                    return struct.unpack(">II", data[:8])
    except OSError:
        return None
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    if path.suffix.lower() == ".png":
        size = _png_size_fast(path)
        if size:
            return size
    apply_pillow_limit()
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except OSError:
        return None


def tile_count(length: int, chunk: int) -> int:
    return (length + chunk - 1) // chunk


def plan_ocr_tiles(w: int, h: int, max_side: int) -> TilePlan:
    if max(w, h) <= max_side and w * h <= ocr_max_pixels():
        return TilePlan(1, "single", f"{w}x{h}")
    if h > max_side and w <= max_side:
        n = tile_count(h, max_side)
        return TilePlan(n, "vertical", f"{w}x{h} -> {n} strips, h<={max_side}")
    if w > max_side and h <= max_side:
        n = tile_count(w, max_side)
        return TilePlan(n, "horizontal", f"{w}x{h} -> {n} strips, w<={max_side}")
    return TilePlan(1, "scale", f"{w}x{h} -> scale to max_side {max_side}")


def _save_png(img, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="PNG", optimize=True)


def _split_image(
    app: App,
    src: Path,
    job_id: str,
    attempt: int,
    chunk: int,
    axis: Axis,
) -> tuple[list[Path], list[Path], int, int]:
    apply_pillow_limit()
    from PIL import Image

    tiles: list[Path] = []
    temps: list[Path] = []
    with Image.open(src) as img:
        w, h = img.size
        pos = 0
        idx = 0
        length = h if axis == "vertical" else w
        while pos < length:
            end = min(pos + chunk, length)
            if axis == "vertical":
                crop = img.crop((0, pos, w, end))
                log_append(app, f"OCR tile {idx}: {w}x{end - pos}")
            else:
                crop = img.crop((pos, 0, end, h))
                log_append(app, f"OCR tile {idx}: {end - pos}x{h}")
            dest = app.work / f"{job_id}_a{attempt}_t{idx:03d}.png"
            _save_png(crop, dest)
            tiles.append(dest)
            temps.append(dest)
            pos = end
            idx += 1
    return tiles, temps, w, h


def _downscale(app: App, src: Path, job_id: str, attempt: int, max_side: int, w: int, h: int) -> Path:
    scale = max_side / max(w, h)
    new_size = (
        max(MIN_OCR_SIDE, int(w * scale)),
        max(MIN_OCR_SIDE, int(h * scale)),
    )
    dest = app.work / f"{job_id}_a{attempt}_scaled.png"
    apply_pillow_limit()
    from PIL import Image

    with Image.open(src) as img:
        _save_png(img.resize(new_size, Image.Resampling.LANCZOS), dest)
    log_append(app, f"OCR downscale: {src.name} {w}x{h} -> {new_size[0]}x{new_size[1]}")
    return dest


def prepare_ocr_inputs(
    app: App,
    src: Path,
    job_id: str,
    attempt: int,
    max_side: int,
) -> OcrPrepareResult:
    size = image_size(src)
    if not size:
        return OcrPrepareResult([src], [], TilePlan(1, "single", "unknown size"))

    w, h = size
    plan = plan_ocr_tiles(w, h, max_side)
    if plan.mode == "single":
        return OcrPrepareResult([src], [], plan)

    if plan.mode == "vertical":
        tiles, temps, _, _ = _split_image(app, src, job_id, attempt, max_side, "vertical")
        log_append(app, f"OCR split vertical: {src.name} {w}x{h} -> {len(tiles)} tiles")
    elif plan.mode == "horizontal":
        tiles, temps, _, _ = _split_image(app, src, job_id, attempt, max_side, "horizontal")
        log_append(app, f"OCR split horizontal: {src.name} {w}x{h} -> {len(tiles)} tiles")
    else:
        dest = _downscale(app, src, job_id, attempt, max_side, w, h)
        return OcrPrepareResult([dest], [dest], plan)

    if len(tiles) != plan.count:
        log_append(app, f"WARN: planned {plan.count} tiles, created {len(tiles)}")
        plan = TilePlan(len(tiles), plan.mode, f"{w}x{h} -> {len(tiles)} strips ({plan.mode})")

    return OcrPrepareResult(tiles, temps, plan)
