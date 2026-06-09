"""Per-file conversion with retries and tiling."""

from __future__ import annotations

import random
import shutil
import time
from pathlib import Path

from docling_batch.config import (
    MAX_ATTEMPTS,
    MIN_TILE_CHARS,
    RETRY_DELAY_SEC,
    SUPPORTED_EXT,
    ocr_max_side_for_attempt,
)
from docling_batch.docling_exec import build_docling_args, conversion_failed, run_docling
from docling_batch.formats import resolve_format
from docling_batch.images import image_size, prepare_ocr_inputs
from docling_batch.io import log_append, say
from docling_batch.models import App, TilePlan
from docling_batch.paths import (
    cleanup_artifacts,
    cleanup_job_artifacts,
    merge_parsed_outputs,
    output_complete,
    output_has_content,
    output_key,
    output_valid,
    remove_unwanted,
    rename_job_outputs,
)


def _finalize_success(app: App, stems: list[str], job_id: str, out_key: str) -> bool:
    if len(stems) == 1:
        rename_job_outputs(app.parsed, stems[0], out_key)
        if output_valid(app.parsed, out_key):
            cleanup_job_artifacts(app.parsed, job_id, out_key)
            return True
        return False
    if merge_parsed_outputs(app.parsed, stems, out_key):
        cleanup_job_artifacts(app.parsed, job_id, out_key)
        return True
    return False


def _process_tiles(
    app: App,
    ocr_inputs: list[Path],
    tile_total: int,
    spec,
    use_ocr: bool,
) -> tuple[list[str], bool]:
    stems_ok: list[str] = []
    for idx, tile_path in enumerate(ocr_inputs):
        if tile_total > 1:
            say(f"     tile {idx + 1}/{tile_total}")
        code, out = run_docling(build_docling_args(app, tile_path, spec, use_ocr), app)
        stem = tile_path.stem
        if conversion_failed(out) or code != 0:
            log_append(app, f"WARN: tile failed {stem}")
            return stems_ok, True
        if output_has_content(app.parsed, stem, MIN_TILE_CHARS) or output_complete(app.parsed, stem):
            stems_ok.append(stem)
        else:
            log_append(app, f"WARN: tile empty or missing output {stem}")
            return stems_ok, True
    return stems_ok, False


def run_with_retry(app: App, src: Path, job_id: str, out_key: str, ext: str) -> bool:
    spec = resolve_format(ext)
    if spec.kind == "unknown":
        return False

    if spec.kind == "image":
        if size := image_size(src):
            w, h = size
            log_append(app, f"Image size: {w}x{h} ({w * h} px)")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        cleanup_job_artifacts(app.parsed, job_id, out_key)

        use_ocr = spec.ocr_first and not (attempt >= 2 and spec.kind == "pdf")
        ocr_inputs: list[Path] = [src]
        ocr_temps: list[Path] = []
        tile_plan = TilePlan(1, "single", "")

        if spec.kind == "image" and use_ocr:
            prep = prepare_ocr_inputs(app, src, job_id, attempt, ocr_max_side_for_attempt(attempt))
            ocr_inputs, ocr_temps, tile_plan = prep.inputs, prep.temps, prep.plan

        tile_total = len(ocr_inputs)
        log_append(
            app,
            f"Attempt {attempt}/{MAX_ATTEMPTS} {spec.kind} job={job_id} out={out_key} "
            f"ocr={'yes' if use_ocr else 'no'} tiles={tile_total}",
        )
        ocr_tag = ", OCR" if use_ocr else ""
        say(f"  -> attempt {attempt}/{MAX_ATTEMPTS} ({spec.kind}{ocr_tag})")
        if tile_total > 1:
            say(f"     tiles: {tile_total} ({tile_plan.label})")

        try:
            stems_ok, failed = _process_tiles(app, ocr_inputs, tile_total, spec, use_ocr)
        finally:
            for temp in ocr_temps:
                temp.unlink(missing_ok=True)

        if not failed and stems_ok and _finalize_success(app, stems_ok, job_id, out_key):
            return True
        if not failed and stems_ok:
            log_append(app, f"WARN: merged output empty for {out_key}")

        if attempt < MAX_ATTEMPTS:
            log_append(app, f"Retry in {RETRY_DELAY_SEC} s...")
            time.sleep(RETRY_DELAY_SEC)

    cleanup_job_artifacts(app.parsed, job_id, out_key)
    return False


def make_work_copy(app: App, src: Path, ext: str) -> tuple[Path, str]:
    job_id = f"job_{app.stats.total}_{random.randint(0, 2_147_483_647)}"
    dest = app.work / f"{job_id}.{ext}"
    try:
        shutil.copy2(src, dest)
        log_append(app, f"Work copy: {dest}")
        return dest, job_id
    except OSError:
        log_append(app, f"Copy fail, direct path: {src}")
        return src, job_id


def handle_file(app: App, src: Path) -> None:
    if src.name.startswith("~$"):
        return

    ext = src.suffix.lstrip(".").lower()
    if not ext or ext not in SUPPORTED_EXT:
        return

    app.stats.total += 1
    key = output_key(src, app.docs)
    if not key:
        return

    if output_valid(app.parsed, key):
        app.stats.skipped += 1
        say(f"[SKIP] {src.name}")
        log_append(app, f"[SKIP] {src}")
        return
    if output_complete(app.parsed, key) and not output_has_content(app.parsed, key):
        log_append(app, f"[REPARSE] empty output for {key}, removing stale files")
        cleanup_artifacts(app.parsed, key)

    say(f"[PARSE] {src.name}")
    log_append(app, f"[PARSE] {src} key={key}")

    work_src, job_id = make_work_copy(app, src, ext)
    ok = run_with_retry(app, work_src, job_id, key, ext)

    if work_src != src and work_src.is_file():
        work_src.unlink(missing_ok=True)

    if not ok:
        app.stats.errors += 1
        say(f"[ERROR] {src.name}")
        log_append(app, f"[ERROR] {src}")
        cleanup_artifacts(app.parsed, job_id)
        cleanup_artifacts(app.parsed, key)
        return

    app.stats.parsed += 1
    say(f"[OK] {src.name}")
    log_append(app, f"[OK] {src}")
    remove_unwanted(app.parsed, job_id)
    remove_unwanted(app.parsed, key)
