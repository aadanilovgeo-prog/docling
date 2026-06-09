#!/usr/bin/env python3
"""
Docling batch parser v3.0.0 — single-file runner.

docs/  ->  parsed/  (.md + .html)
"""

from __future__ import annotations

import argparse
import io
import os

os.environ.setdefault("PILLOW_MAX_IMAGE_PIXELS", "9999999999")

import random
import re
import shutil
import struct
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Literal

VERSION = "3.0.0"

DEFAULT_PILLOW = "9999999999"
DEFAULT_OCR_MAX_PIXELS = 50_000_000
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
Axis = Literal["vertical", "horizontal"]

_runtime: "DoclingRuntime | None" = None

_TABLES = ["--tables", "--table-mode", "accurate"]
_ASR = ["--pipeline", "asr", "--asr-model", "whisper_tiny"]


@dataclass
class FormatSpec:
    kind: str = "unknown"
    from_arg: list[str] = field(default_factory=list)
    pipeline: list[str] = field(default_factory=list)
    pdf: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=lambda: ["--no-tables"])
    ocr_first: bool = False


@dataclass
class DoclingRuntime:
    mode: str
    python: Path
    label: str


@dataclass
class Stats:
    total: int = 0
    parsed: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class TilePlan:
    count: int
    mode: str
    label: str


@dataclass
class OcrPrepareResult:
    inputs: list[Path]
    temps: list[Path]
    plan: TilePlan


@dataclass
class App:
    root: Path
    docs: Path
    parsed: Path
    logs: Path
    work: Path
    tmp: Path
    log_file: Path
    stats: Stats = field(default_factory=Stats)

    @classmethod
    def from_root(cls, root: Path) -> App:
        root = root.resolve()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(
            root=root,
            docs=root / "docs",
            parsed=root / "parsed",
            logs=root / "logs",
            work=root / "work",
            tmp=root / "work" / "tmp",
            log_file=root / "logs" / f"docling_{stamp}_{random.randint(0, 9999)}.log",
        )


_FORMATS: dict[str, FormatSpec] = {
    "pdf": FormatSpec(
        kind="pdf", from_arg=["--from", "pdf"], pdf=["--pdf-backend", "pypdfium2"],
        tables=_TABLES, ocr_first=True,
    ),
    "docx": FormatSpec(kind="office", from_arg=["--from", "docx"], tables=_TABLES),
    "xlsx": FormatSpec(kind="office", from_arg=["--from", "xlsx"], tables=_TABLES),
    "pptx": FormatSpec(kind="office", from_arg=["--from", "pptx"], tables=_TABLES),
    "md": FormatSpec(kind="text", from_arg=["--from", "md"]),
    "markdown": FormatSpec(kind="text", from_arg=["--from", "md"]),
    "adoc": FormatSpec(kind="text", from_arg=["--from", "asciidoc"]),
    "asciidoc": FormatSpec(kind="text", from_arg=["--from", "asciidoc"]),
    "tex": FormatSpec(kind="text", from_arg=["--from", "latex"]),
    "html": FormatSpec(kind="text", from_arg=["--from", "html"]),
    "htm": FormatSpec(kind="text", from_arg=["--from", "html"]),
    "xhtml": FormatSpec(kind="text", from_arg=["--from", "html"]),
    "csv": FormatSpec(kind="text", from_arg=["--from", "csv"], tables=_TABLES),
    "vtt": FormatSpec(kind="text", from_arg=["--from", "vtt"]),
    "json": FormatSpec(kind="json", from_arg=["--from", "json_docling"]),
    "xml": FormatSpec(kind="xml"),
    "png": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "jpg": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "jpeg": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "tif": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "tiff": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "bmp": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "webp": FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True),
    "wav": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "mp3": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "m4a": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "aac": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "ogg": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "flac": FormatSpec(kind="audio", from_arg=["--from", "audio"], pipeline=_ASR),
    "mp4": FormatSpec(kind="video", from_arg=["--from", "audio"], pipeline=_ASR),
    "avi": FormatSpec(kind="video", from_arg=["--from", "audio"], pipeline=_ASR),
    "mov": FormatSpec(kind="video", from_arg=["--from", "audio"], pipeline=_ASR),
}


def resolve_format(ext: str) -> FormatSpec:
    return _FORMATS.get(ext.lower(), FormatSpec())


def pillow_limit() -> str:
    return (
        os.environ.get("DOCLING_PILLOW_MAX_PIXELS")
        or os.environ.get("PILLOW_MAX_IMAGE_PIXELS")
        or DEFAULT_PILLOW
    )


def apply_pillow_limit() -> None:
    val = pillow_limit()
    os.environ["PILLOW_MAX_IMAGE_PIXELS"] = val
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = int(val)
    except (ImportError, ValueError, OverflowError):
        pass


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


def say(msg: str = "") -> None:
    print(msg, flush=True)


def log_append(app: App, line: str) -> None:
    app.log_file.parent.mkdir(parents=True, exist_ok=True)
    with app.log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_cmd(app: App, parts: list[str]) -> None:
    log_append(app, "CMD " + " ".join(f'"{p}"' if " " in p else p for p in parts))


def write_log_output(app: App, output: str) -> None:
    if output:
        with app.log_file.open("a", encoding="utf-8") as lf:
            lf.write(output)


def ensure_dirs(app: App) -> None:
    for p in (app.work, app.tmp, app.docs, app.parsed, app.logs):
        p.mkdir(parents=True, exist_ok=True)


def output_key(src: Path, docs: Path) -> str:
    docs = docs.resolve()
    src = src.resolve()
    try:
        rel = src.parent.relative_to(docs)
    except ValueError:
        return src.stem
    return "_".join([*rel.parts, src.stem])


def _pair(parsed: Path, key: str, ext: str) -> Path:
    return parsed / f"{key}{ext}"


def output_complete(parsed: Path, key: str) -> bool:
    return _pair(parsed, key, ".md").is_file() and _pair(parsed, key, ".html").is_file()


def output_has_content(parsed: Path, key: str, min_chars: int = MIN_OUTPUT_CHARS) -> bool:
    md_path = _pair(parsed, key, ".md")
    html_path = _pair(parsed, key, ".html")
    if not md_path.is_file() or not html_path.is_file():
        return False
    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace").strip()
        html_text = html_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    if len(md_text) >= min_chars:
        return True
    html_plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text)).strip()
    return len(html_plain) >= min_chars


def output_valid(parsed: Path, key: str) -> bool:
    return output_complete(parsed, key) and output_has_content(parsed, key)


def cleanup_artifacts(parsed: Path, key: str) -> None:
    if not key:
        return
    for suffix in OUTPUT_SUFFIXES:
        _pair(parsed, key, suffix).unlink(missing_ok=True)
    shutil.rmtree(parsed / key, ignore_errors=True)


def cleanup_job_artifacts(parsed: Path, job_id: str, out_key: str) -> None:
    cleanup_artifacts(parsed, job_id)
    cleanup_artifacts(parsed, out_key)
    for path in list(parsed.glob(f"{job_id}_*")):
        if path.is_file() and path.suffix in OUTPUT_SUFFIXES:
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def remove_unwanted(parsed: Path, key: str) -> None:
    if not key:
        return
    for suffix in (".json", ".txt"):
        _pair(parsed, key, suffix).unlink(missing_ok=True)
    shutil.rmtree(parsed / key, ignore_errors=True)
    shutil.rmtree(parsed / f"{key}_artifacts", ignore_errors=True)


def rename_job_outputs(parsed: Path, job_id: str, out_key: str) -> None:
    if job_id.lower() == out_key.lower():
        return
    for ext in (".md", ".html"):
        src = _pair(parsed, job_id, ext)
        dst = _pair(parsed, out_key, ext)
        if src.is_file():
            dst.unlink(missing_ok=True)
            src.rename(dst)


def merge_parsed_outputs(parsed: Path, stems: list[str], out_key: str) -> bool:
    md_parts: list[str] = []
    html_parts: list[str] = []
    for stem in stems:
        md_path = _pair(parsed, stem, ".md")
        html_path = _pair(parsed, stem, ".html")
        if md_path.is_file():
            text = md_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                md_parts.append(text)
        if html_path.is_file():
            text = html_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                html_parts.append(text)
    if not md_parts and not html_parts:
        return False
    _pair(parsed, out_key, ".md").write_text("\n\n---\n\n".join(md_parts), encoding="utf-8")
    if html_parts:
        body = "\n<hr/>\n".join(html_parts)
        if not re.search(r"<html\b", body, re.I):
            body = f"<!DOCTYPE html>\n<html><body>\n{body}\n</body></html>"
        _pair(parsed, out_key, ".html").write_text(body, encoding="utf-8")
    else:
        _pair(parsed, out_key, ".html").write_text(
            "<!DOCTYPE html>\n<html><body></body></html>", encoding="utf-8",
        )
    for stem in stems:
        if stem != out_key:
            cleanup_artifacts(parsed, stem)
    return output_valid(parsed, out_key)


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
        if size := _png_size_fast(path):
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
    app: App, src: Path, job_id: str, attempt: int, chunk: int, axis: Axis,
) -> tuple[list[Path], list[Path]]:
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
            crop = img.crop((0, pos, w, end) if axis == "vertical" else (pos, 0, end, h))
            log_append(app, f"OCR tile {idx}: {w}x{end - pos}" if axis == "vertical" else f"OCR tile {idx}: {end - pos}x{h}")
            dest = app.work / f"{job_id}_a{attempt}_t{idx:03d}.png"
            _save_png(crop, dest)
            tiles.append(dest)
            temps.append(dest)
            pos = end
            idx += 1
    return tiles, temps


def _downscale(app: App, src: Path, job_id: str, attempt: int, max_side: int, w: int, h: int) -> Path:
    scale = max_side / max(w, h)
    new_size = (max(MIN_OCR_SIDE, int(w * scale)), max(MIN_OCR_SIDE, int(h * scale)))
    dest = app.work / f"{job_id}_a{attempt}_scaled.png"
    apply_pillow_limit()
    from PIL import Image
    with Image.open(src) as img:
        _save_png(img.resize(new_size, Image.Resampling.LANCZOS), dest)
    log_append(app, f"OCR downscale: {src.name} {w}x{h} -> {new_size[0]}x{new_size[1]}")
    return dest


def prepare_ocr_inputs(app: App, src: Path, job_id: str, attempt: int, max_side: int) -> OcrPrepareResult:
    size = image_size(src)
    if not size:
        return OcrPrepareResult([src], [], TilePlan(1, "single", "unknown size"))
    w, h = size
    plan = plan_ocr_tiles(w, h, max_side)
    if plan.mode == "single":
        return OcrPrepareResult([src], [], plan)
    if plan.mode == "vertical":
        tiles, temps = _split_image(app, src, job_id, attempt, max_side, "vertical")
        log_append(app, f"OCR split vertical: {src.name} {w}x{h} -> {len(tiles)} tiles")
    elif plan.mode == "horizontal":
        tiles, temps = _split_image(app, src, job_id, attempt, max_side, "horizontal")
        log_append(app, f"OCR split horizontal: {src.name} {w}x{h} -> {len(tiles)} tiles")
    else:
        dest = _downscale(app, src, job_id, attempt, max_side, w, h)
        return OcrPrepareResult([dest], [dest], plan)
    if len(tiles) != plan.count:
        log_append(app, f"WARN: planned {plan.count} tiles, created {len(tiles)}")
        plan = TilePlan(len(tiles), plan.mode, f"{w}x{h} -> {len(tiles)} strips ({plan.mode})")
    return OcrPrepareResult(tiles, temps, plan)


def _subprocess_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


@lru_cache(maxsize=1)
def _conda_roots() -> tuple[Path, ...]:
    seen: set[str] = set()
    roots: list[Path] = []

    def add(path: Path) -> None:
        if not path.is_dir():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    if local := os.environ.get("LOCALAPPDATA"):
        for name in ("miniconda3", "anaconda3"):
            add(Path(local) / name)
            add(Path(local) / "Programs" / name)
    for rel in ("AppData/Local/miniconda3", "AppData/Local/Programs/miniconda3",
                "AppData/Local/anaconda3", "miniconda3", "Anaconda3"):
        add(Path.home() / rel)
    if cp := os.environ.get("CONDA_PREFIX"):
        add(Path(cp))
    return tuple(roots)


def augment_conda_path() -> None:
    extra: list[str] = []
    for root in _conda_roots():
        extra.append(str(root))
        if (scripts := root / "Scripts").is_dir():
            extra.append(str(scripts))
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")


@lru_cache(maxsize=1)
def _docling_exe_paths() -> tuple[Path, ...]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    if hit := shutil.which("docling"):
        add(Path(hit))
    for root in _conda_roots():
        add(root / "Scripts" / "docling.exe")
    return tuple(found)


def _python_for_docling_exe(docling_exe: Path) -> Path | None:
    scripts = docling_exe.parent
    for candidate in (scripts / "python.exe", scripts.parent / "python.exe"):
        if candidate.is_file():
            return candidate
    return None


def _python_has_docling(py: Path) -> bool:
    try:
        proc = subprocess.run(
            [str(py), "-c", "import docling.cli.main"],
            capture_output=True, timeout=120, creationflags=_subprocess_flags(),
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _iter_python_candidates() -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []

    def offer(path: Path) -> None:
        if not path.is_file():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        result.append(path)

    if env_py := os.environ.get("DOCLING_PYTHON"):
        offer(Path(env_py))
    for doc in _docling_exe_paths():
        if py := _python_for_docling_exe(doc):
            offer(py)
    for root in _conda_roots():
        offer(root / "python.exe")
    offer(Path(sys.executable))
    return result


def resolve_docling_runtime() -> DoclingRuntime | None:
    global _runtime
    if _runtime is not None:
        return _runtime
    augment_conda_path()
    trusted = {py.resolve() for doc in _docling_exe_paths() if (py := _python_for_docling_exe(doc))}
    for py in _iter_python_candidates():
        if py.resolve() in trusted or _python_has_docling(py):
            if py.resolve() == Path(sys.executable).resolve():
                _runtime = DoclingRuntime("inprocess", py, f"in-process ({py})")
            else:
                _runtime = DoclingRuntime("subprocess", py, f"subprocess ({py})")
            return _runtime
    return None


def docling_runner_path() -> Path:
    return Path(__file__).resolve().parent / "_docling_runner.py"


def build_docling_args(app: App, src: Path, spec: FormatSpec, use_ocr: bool) -> list[str]:
    image_mode = "embedded" if spec.kind == "image" else "placeholder"
    args = [
        "--to", "md", "--to", "html", "--output", str(app.parsed),
        *spec.from_arg, *spec.pipeline, *spec.pdf,
        "--ocr" if use_ocr else "--no-ocr", *spec.tables,
        "--image-export-mode", image_mode, "-v", str(src),
    ]
    if spec.kind == "image" and use_ocr:
        args.append("--force-ocr")
    return args


def child_env(app: App) -> dict[str, str]:
    env = os.environ.copy()
    env["PILLOW_MAX_IMAGE_PIXELS"] = pillow_limit()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["TEMP"] = str(app.tmp)
    env["TMP"] = str(app.tmp)
    return env


def conversion_failed(output: str) -> bool:
    return any(m in output for m in CONVERSION_FAILURE_MARKERS)


def run_docling_inprocess(args: list[str], app: App) -> tuple[int, str]:
    apply_pillow_limit()
    buf = io.StringIO()
    old_argv = sys.argv[:]
    sys.argv = ["docling", *args]
    code = 0
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            from docling.cli.main import app as cli_app
            try:
                cli_app()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception:
        import traceback
        traceback.print_exc(file=buf)
        code = 1
    finally:
        sys.argv = old_argv
    write_log_output(app, buf.getvalue())
    return code, buf.getvalue()


def run_docling_subprocess(runtime: DoclingRuntime, args: list[str], app: App) -> tuple[int, str]:
    cmd = [str(runtime.python), "-u", str(docling_runner_path()), *args]
    log_cmd(app, cmd)
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(app.root), env=child_env(app), text=True,
        encoding="utf-8", errors="replace", creationflags=_subprocess_flags(),
    )
    out = proc.stdout or ""
    write_log_output(app, out)
    log_append(app, f"EXIT {proc.returncode}")
    return proc.returncode, out


def run_docling(args: list[str], app: App) -> tuple[int, str]:
    runtime = resolve_docling_runtime()
    if runtime is None:
        return 1, "ERROR: docling runtime not resolved"
    log_cmd(app, ["docling", *args])
    log_append(app, f"PILLOW_MAX_IMAGE_PIXELS={pillow_limit()}")
    log_append(app, f"Mode: {runtime.label}")
    if runtime.mode == "inprocess":
        code, out = run_docling_inprocess(args, app)
        log_append(app, f"EXIT {code}")
        return code, out
    return run_docling_subprocess(runtime, args, app)


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
    app: App, ocr_inputs: list[Path], tile_total: int, spec: FormatSpec, use_ocr: bool,
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
    if spec.kind == "image" and (size := image_size(src)):
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Docling batch parse v{VERSION}: docs/ -> parsed/ (md + html)",
    )
    parser.add_argument("--root", type=Path, default=None, help="Project root")
    parser.add_argument("--python", type=Path, default=None, help="Python with docling")
    parser.add_argument("--pause", action="store_true", help="Wait for Enter before exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.python:
        os.environ["DOCLING_PYTHON"] = str(args.python)
    if args.root is not None:
        root = args.root
    elif env_root := os.environ.get("DOCLING_ROOT"):
        root = Path(env_root)
    else:
        root = Path(__file__).resolve().parent

    app = App.from_root(root)
    apply_pillow_limit()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["TEMP"] = str(app.tmp)
    os.environ["TMP"] = str(app.tmp)
    ensure_dirs(app)
    app.log_file.touch()

    script = Path(__file__).resolve()
    say("========================================")
    say(f"Docling batch parse - v{VERSION} (Python)")
    say("========================================")
    say(f"Script: {script}")
    say(f"Root:   {app.root}")
    say("Vyhod:  md + html")
    say("========================================")
    say("Proverka papok...")
    say("  docs, parsed, logs, work - OK")
    say("")

    log_append(app, f"Started v{VERSION}")
    log_append(app, f"PILLOW_MAX_IMAGE_PIXELS={pillow_limit()}")
    log_append(app, f"Script Python: {sys.executable}")

    runtime = resolve_docling_runtime()
    if runtime is None:
        say("OSHIBKA: docling ne naiden.")
        say("  pip install docling")
        say("  set DOCLING_PYTHON=%LOCALAPPDATA%\\miniconda3\\python.exe")
        log_append(app, "ERROR: docling not found")
        for doc in _docling_exe_paths():
            log_append(app, f"  found docling.exe: {doc}")
        for py in _iter_python_candidates():
            log_append(app, f"  tried python: {py}")
        if args.pause:
            input("Enter...")
        return 1

    say(f"Docling: {runtime.label}")
    log_append(app, f"Docling runtime: {runtime.label}")
    say(f"Input:   {app.docs}")
    say(f"Output:  {app.parsed}")
    say(f"Log:     {app.log_file}")
    say("")
    say("Skanirovanie...")
    say("")

    for path in sorted(app.docs.rglob("*")):
        if path.is_file():
            handle_file(app, path)

    say("")
    say("========================================")
    say("ITOGOVYY OTCHET")
    say("========================================")
    say(f"Total files found: {app.stats.total}")
    say(f"Parsed:            {app.stats.parsed}")
    say(f"Skipped:           {app.stats.skipped}")
    say(f"Errors:            {app.stats.errors}")
    say("========================================")
    if app.stats.total == 0:
        say("VNIMANIE: fajly ne najdeny v docs")
    say("")
    say("Log file:")
    say(str(app.log_file))
    log_append(
        app,
        f"Done T={app.stats.total} P={app.stats.parsed} S={app.stats.skipped} E={app.stats.errors}",
    )
    if args.pause:
        say("")
        input("Gotovo. Nazhmite Enter...")
    return 1 if app.stats.errors else 0


if __name__ == "__main__":
    if sys.platform == "win32" and len(sys.argv) == 1:
        sys.argv.append("--pause")
    raise SystemExit(main())
