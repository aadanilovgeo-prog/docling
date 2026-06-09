#!/usr/bin/env python3
"""
Docling batch parser v2.0.6 — Python port of BAT v1.6 logic.

docs/  ->  parsed/  (.md + .html)
"""

from __future__ import annotations

import os

# Must be set before Pillow is imported (in this process or child python -m docling).
os.environ.setdefault("PILLOW_MAX_IMAGE_PIXELS", "9999999999")

import argparse
import re
import random
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

VERSION = "2.0.6"

_runtime: "DoclingRuntime | None" = None
DEFAULT_PILLOW = "9999999999"
DEFAULT_OCR_MAX_PIXELS = 50_000_000
DEFAULT_OCR_MAX_SIDE = 8192
OCR_MAX_SIDES = (8192, 4096, 2048)
MIN_OUTPUT_CHARS = 32
MAX_ATTEMPTS = 3
RETRY_DELAY_SEC = 5

SUPPORTED_EXT = {
    "pdf", "docx", "xlsx", "pptx",
    "md", "markdown", "adoc", "asciidoc", "tex",
    "html", "htm", "xhtml", "csv", "vtt",
    "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp",
    "wav", "mp3", "m4a", "aac", "ogg", "flac",
    "mp4", "avi", "mov", "json", "xml",
}


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
    mode: str  # inprocess | subprocess
    python: Path
    label: str


@dataclass
class Stats:
    total: int = 0
    parsed: int = 0
    skipped: int = 0
    errors: int = 0


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
        return cls(
            root=root,
            docs=root / "docs",
            parsed=root / "parsed",
            logs=root / "logs",
            work=root / "work",
            tmp=root / "work" / "tmp",
            log_file=root / "logs" / f"docling_{datetime.now():%Y%m%d_%H%M%S}_{random.randint(0, 9999)}.log",
        )


def resolve_format(ext: str) -> FormatSpec:
    e = ext.lower()
    spec = FormatSpec()

    if e == "pdf":
        return FormatSpec(
            kind="pdf",
            from_arg=["--from", "pdf"],
            pdf=["--pdf-backend", "pypdfium2"],
            tables=["--tables", "--table-mode", "accurate"],
            ocr_first=True,
        )
    if e == "docx":
        return FormatSpec(kind="office", from_arg=["--from", "docx"], tables=["--tables", "--table-mode", "accurate"])
    if e == "xlsx":
        return FormatSpec(kind="office", from_arg=["--from", "xlsx"], tables=["--tables", "--table-mode", "accurate"])
    if e == "pptx":
        return FormatSpec(kind="office", from_arg=["--from", "pptx"], tables=["--tables", "--table-mode", "accurate"])
    if e in ("md", "markdown"):
        return FormatSpec(kind="text", from_arg=["--from", "md"])
    if e in ("adoc", "asciidoc"):
        return FormatSpec(kind="text", from_arg=["--from", "asciidoc"])
    if e == "tex":
        return FormatSpec(kind="text", from_arg=["--from", "latex"])
    if e in ("html", "htm", "xhtml"):
        return FormatSpec(kind="text", from_arg=["--from", "html"])
    if e == "csv":
        return FormatSpec(kind="text", from_arg=["--from", "csv"], tables=["--tables", "--table-mode", "accurate"])
    if e == "vtt":
        return FormatSpec(kind="text", from_arg=["--from", "vtt"])
    if e == "json":
        return FormatSpec(kind="json", from_arg=["--from", "json_docling"])
    if e == "xml":
        return FormatSpec(kind="xml")
    if e in ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"):
        return FormatSpec(kind="image", from_arg=["--from", "image"], ocr_first=True)
    if e in ("wav", "mp3", "m4a", "aac", "ogg", "flac"):
        return FormatSpec(
            kind="audio",
            from_arg=["--from", "audio"],
            pipeline=["--pipeline", "asr", "--asr-model", "whisper_tiny"],
        )
    if e in ("mp4", "avi", "mov"):
        return FormatSpec(
            kind="video",
            from_arg=["--from", "audio"],
            pipeline=["--pipeline", "asr", "--asr-model", "whisper_tiny"],
        )
    return spec


def output_key(src: Path, docs: Path) -> str:
    docs = docs.resolve()
    src = src.resolve()
    try:
        rel = src.parent.relative_to(docs)
    except ValueError:
        return src.stem
    parts = list(rel.parts) + [src.stem]
    return "_".join(parts)


def output_complete(parsed: Path, key: str) -> bool:
    return (parsed / f"{key}.md").is_file() and (parsed / f"{key}.html").is_file()


def output_has_content(parsed: Path, key: str, min_chars: int = MIN_OUTPUT_CHARS) -> bool:
    md_path = parsed / f"{key}.md"
    html_path = parsed / f"{key}.html"
    if not md_path.is_file() or not html_path.is_file():
        return False
    try:
        md_text = md_path.read_text(encoding="utf-8", errors="replace").strip()
        html_text = html_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    if len(md_text) >= min_chars:
        return True
    html_plain = re.sub(r"<[^>]+>", " ", html_text)
    html_plain = re.sub(r"\s+", " ", html_plain).strip()
    return len(html_plain) >= min_chars


def output_valid(parsed: Path, key: str) -> bool:
    return output_complete(parsed, key) and output_has_content(parsed, key)


def cleanup_artifacts(parsed: Path, key: str) -> None:
    if not key:
        return
    for name in (f"{key}.md", f"{key}.html", f"{key}.json", f"{key}.txt"):
        (parsed / name).unlink(missing_ok=True)
    shutil.rmtree(parsed / key, ignore_errors=True)


def remove_unwanted(parsed: Path, key: str) -> None:
    if not key:
        return
    for name in (f"{key}.json", f"{key}.txt"):
        (parsed / name).unlink(missing_ok=True)
    shutil.rmtree(parsed / key, ignore_errors=True)
    shutil.rmtree(parsed / f"{key}_artifacts", ignore_errors=True)


def rename_job_outputs(parsed: Path, job_id: str, out_key: str) -> None:
    if job_id.lower() == out_key.lower():
        return
    for ext in (".md", ".html"):
        src = parsed / f"{job_id}{ext}"
        dst = parsed / f"{out_key}{ext}"
        if src.is_file():
            dst.unlink(missing_ok=True)
            src.rename(dst)


def log_append(app: App, line: str) -> None:
    app.log_file.parent.mkdir(parents=True, exist_ok=True)
    with app.log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def say(msg: str = "") -> None:
    print(msg, flush=True)


def ensure_dirs(app: App) -> None:
    for p in (app.work, app.tmp, app.docs, app.parsed, app.logs):
        p.mkdir(parents=True, exist_ok=True)


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


def image_size(path: Path) -> tuple[int, int] | None:
    """Read dimensions without full decode when possible (PNG IHDR)."""
    try:
        if path.suffix.lower() == ".png":
            with path.open("rb") as f:
                if f.read(8) == b"\x89PNG\r\n\x1a\n":
                    while True:
                        header = f.read(8)
                        if len(header) < 8:
                            break
                        length, ctype = struct.unpack(">I4s", header)
                        data = f.read(length)
                        f.read(4)
                        if ctype == b"IHDR" and len(data) >= 8:
                            return struct.unpack(">II", data[:8])
        apply_pillow_limit()
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except OSError:
        return None


def image_pixel_count(path: Path) -> int | None:
    size = image_size(path)
    if not size:
        return None
    w, h = size
    return w * h


def prepare_ocr_image(app: App, src: Path, job_id: str, attempt: int, max_side: int) -> tuple[Path, Path | None]:
    """Downscale huge images so OCR can run; returns (input_path, temp_path_or_none)."""
    size = image_size(src)
    if not size:
        return src, None
    w, h = size
    if max(w, h) <= max_side:
        return src, None

    scale = max_side / max(w, h)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    dest = app.work / f"{job_id}_ocr_a{attempt}.png"
    apply_pillow_limit()
    from PIL import Image

    with Image.open(src) as img:
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        resized.save(dest, format="PNG", optimize=True)
    log_append(
        app,
        f"OCR downscale: {src.name} {w}x{h} -> {new_size[0]}x{new_size[1]} ({dest.name})",
    )
    return dest, dest


def docling_runner_path() -> Path:
    return Path(__file__).resolve().parent / "_docling_runner.py"


def _subprocess_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


def python_has_docling(py: Path) -> bool:
    try:
        proc = subprocess.run(
            [str(py), "-c", "import docling.cli.main"],
            capture_output=True,
            timeout=120,
            creationflags=_subprocess_flags(),
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _conda_roots() -> Iterator[Path]:
    """Common miniconda/anaconda install roots (double-click often has no PATH)."""
    seen: set[str] = set()

    def offer(path: Path) -> Iterator[Path]:
        if not path.is_dir():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        yield path

    if local := os.environ.get("LOCALAPPDATA"):
        yield from offer(Path(local) / "miniconda3")
        yield from offer(Path(local) / "Programs" / "miniconda3")
        yield from offer(Path(local) / "anaconda3")
        yield from offer(Path(local) / "Programs" / "anaconda3")

    home = Path.home()
    for rel in (
        "AppData/Local/miniconda3",
        "AppData/Local/Programs/miniconda3",
        "AppData/Local/anaconda3",
        "miniconda3",
        "Anaconda3",
    ):
        yield from offer(home / rel)

    if cp := os.environ.get("CONDA_PREFIX"):
        yield from offer(Path(cp))


def augment_conda_path() -> None:
    """Double-click often misses miniconda in PATH — add common locations."""
    extra: list[str] = []
    for root in _conda_roots():
        extra.append(str(root))
        scripts = root / "Scripts"
        if scripts.is_dir():
            extra.append(str(scripts))
    cp = os.environ.get("CONDA_PREFIX")
    if cp:
        extra.extend([str(Path(cp) / "Scripts"), cp])
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")


def find_docling_exe_paths() -> list[Path]:
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

    hit = shutil.which("docling")
    if hit:
        add(Path(hit))

    for root in _conda_roots():
        add(root / "Scripts" / "docling.exe")

    return found


def python_for_docling_exe(docling_exe: Path) -> Path | None:
    """conda: Scripts\\docling.exe + ..\\python.exe ; venv: Scripts\\python.exe"""
    scripts = docling_exe.parent
    for candidate in (scripts / "python.exe", scripts.parent / "python.exe"):
        if candidate.is_file():
            return candidate
    return None


def iter_python_candidates() -> Iterator[Path]:
    seen: set[str] = set()

    def offer(path: Path) -> Iterator[Path]:
        if not path.is_file():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        yield path

    if env_py := os.environ.get("DOCLING_PYTHON"):
        yield from offer(Path(env_py))

    for doc in find_docling_exe_paths():
        py = python_for_docling_exe(doc)
        if py:
            yield from offer(py)

    for root in _conda_roots():
        yield from offer(root / "python.exe")

    yield from offer(Path(sys.executable))


def _make_runtime(py: Path) -> DoclingRuntime:
    if py.resolve() == Path(sys.executable).resolve():
        return DoclingRuntime("inprocess", py, f"in-process ({py})")
    return DoclingRuntime("subprocess", py, f"subprocess ({py})")


def resolve_docling_runtime() -> DoclingRuntime | None:
    """Find Python for docling. Never use docling.exe (PILLOW env is lost)."""
    global _runtime
    if _runtime is not None:
        return _runtime

    augment_conda_path()

    trusted: list[Path] = []
    for doc in find_docling_exe_paths():
        py = python_for_docling_exe(doc)
        if py:
            trusted.append(py.resolve())

    for py in iter_python_candidates():
        if py.resolve() in trusted or python_has_docling(py):
            _runtime = _make_runtime(py)
            return _runtime

    return None


def child_env(app: App) -> dict[str, str]:
    env = os.environ.copy()
    env["PILLOW_MAX_IMAGE_PIXELS"] = pillow_limit()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["TEMP"] = str(app.tmp)
    env["TMP"] = str(app.tmp)
    return env


def build_docling_args(
    app: App,
    src: Path,
    spec: FormatSpec,
    use_ocr: bool,
) -> list[str]:
    image_mode = "embedded" if spec.kind == "image" else "placeholder"
    args = [
        "--to", "md",
        "--to", "html",
        "--output", str(app.parsed),
        *spec.from_arg,
        *spec.pipeline,
        *spec.pdf,
        "--ocr" if use_ocr else "--no-ocr",
        *spec.tables,
        "--image-export-mode", image_mode,
        "-v", str(src),
    ]
    if spec.kind == "image" and use_ocr:
        args.append("--force-ocr")
    return args


def _write_log_output(app: App, output: str) -> None:
    if output:
        with app.log_file.open("a", encoding="utf-8") as lf:
            lf.write(output)


def run_docling_inprocess(args: list[str], app: App) -> tuple[int, str]:
    """Run docling CLI in this process — PILLOW limit applied before import."""
    apply_pillow_limit()
    import io
    from contextlib import redirect_stderr, redirect_stdout

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
                if isinstance(exc.code, int):
                    code = exc.code
                elif exc.code is None:
                    code = 0
                else:
                    code = 1
    except Exception:
        import traceback

        traceback.print_exc(file=buf)
        code = 1
    finally:
        sys.argv = old_argv

    output = buf.getvalue()
    _write_log_output(app, output)
    return code, output


def run_docling_subprocess_cmd(cmd: list[str], app: App) -> tuple[int, str]:
    log_append(app, "CMD " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(app.root),
        env=child_env(app),
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_subprocess_flags(),
    )
    out = proc.stdout or ""
    _write_log_output(app, out)
    log_append(app, f"EXIT {proc.returncode}")
    return proc.returncode, out


def build_subprocess_cmd(runtime: DoclingRuntime, args: list[str]) -> list[str]:
    runner = docling_runner_path()
    return [str(runtime.python), "-u", str(runner), *args]


def run_docling(args: list[str], app: App) -> tuple[int, str]:
    runtime = resolve_docling_runtime()
    if runtime is None:
        return 1, "ERROR: docling runtime not resolved"

    log_append(app, "CMD docling " + " ".join(f'"{a}"' if " " in a else a for a in args))
    log_append(app, f"PILLOW_MAX_IMAGE_PIXELS={pillow_limit()}")
    log_append(app, f"Mode: {runtime.label}")

    if runtime.mode == "inprocess":
        code, out = run_docling_inprocess(args, app)
        log_append(app, f"EXIT {code}")
        return code, out

    cmd = build_subprocess_cmd(runtime, args)
    return run_docling_subprocess_cmd(cmd, app)


def conversion_failed(output: str) -> bool:
    markers = (
        "DecompressionBombError",
        "ResizeImgError",
        "failed to convert",
        "is not valid",
        "Could not load image",
        "No module named docling",
        "cannot be directly executed",
    )
    return any(m in output for m in markers)


def run_with_retry(app: App, src: Path, job_id: str, out_key: str, ext: str) -> bool:
    spec = resolve_format(ext)
    if spec.kind == "unknown":
        return False

    if spec.kind == "image":
        size = image_size(src)
        if size:
            w, h = size
            log_append(app, f"Image size: {w}x{h} ({w * h} px)")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        cleanup_artifacts(app.parsed, job_id)
        cleanup_artifacts(app.parsed, out_key)

        use_ocr = spec.ocr_first
        if attempt >= 2 and spec.kind == "pdf":
            use_ocr = False

        docling_src = src
        scaled_tmp: Path | None = None
        if spec.kind == "image" and use_ocr:
            max_side = ocr_max_side_for_attempt(attempt)
            docling_src, scaled_tmp = prepare_ocr_image(app, src, job_id, attempt, max_side)

        log_append(
            app,
            f"Attempt {attempt}/{MAX_ATTEMPTS} {spec.kind} job={job_id} out={out_key} ocr={'yes' if use_ocr else 'no'}",
        )
        ocr_tag = ", OCR" if use_ocr else ""
        say(f"  -> attempt {attempt}/{MAX_ATTEMPTS} ({spec.kind}{ocr_tag})")

        code, out = run_docling(build_docling_args(app, docling_src, spec, use_ocr), app)
        if scaled_tmp and scaled_tmp.is_file():
            scaled_tmp.unlink(missing_ok=True)

        if conversion_failed(out):
            log_append(app, "WARN: docling reported conversion failure in output")
        if code == 0 and not conversion_failed(out):
            if output_valid(app.parsed, job_id):
                rename_job_outputs(app.parsed, job_id, out_key)
                if output_valid(app.parsed, out_key):
                    remove_unwanted(app.parsed, job_id)
                    remove_unwanted(app.parsed, out_key)
                    return True
                log_append(app, f"WARN: empty output after rename for {out_key}")
            elif output_complete(app.parsed, job_id):
                log_append(app, f"WARN: docling ok but output empty for {job_id}")
            else:
                log_append(app, f"WARN: docling ok but missing output for {out_key}")

        if attempt < MAX_ATTEMPTS:
            log_append(app, f"Retry in {RETRY_DELAY_SEC} s...")
            time.sleep(RETRY_DELAY_SEC)

    cleanup_artifacts(app.parsed, job_id)
    cleanup_artifacts(app.parsed, out_key)
    return False


def make_work_copy(app: App, src: Path, ext: str, out_key: str) -> tuple[Path, str]:
    job_id = f"job_{app.stats.total}_{random.randint(0, 2_147_483_647)}"
    dest = app.work / f"{job_id}.{ext}"
    try:
        shutil.copy2(src, dest)
        log_append(app, f"Work copy: {dest}")
        return dest, job_id
    except OSError:
        log_append(app, f"Copy fail, direct path: {src}")
        return src, out_key


def iter_files(docs: Path) -> Iterator[Path]:
    for path in sorted(docs.rglob("*")):
        if path.is_file():
            yield path


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

    work_src, job_id = make_work_copy(app, src, ext, key)
    if not work_src:
        app.stats.errors += 1
        say(f"[ERROR] {src.name}")
        log_append(app, "[ERROR] no work file")
        return

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


def setup_env(app: App) -> None:
    apply_pillow_limit()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["TEMP"] = str(app.tmp)
    os.environ["TMP"] = str(app.tmp)


def check_docling() -> bool:
    return resolve_docling_runtime() is not None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Docling batch parse v{VERSION}: docs/ -> parsed/ (md + html)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (default: script dir or DOCLING_ROOT)",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=None,
        help="Python with docling (or set DOCLING_PYTHON)",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Wait for Enter before exit (Windows double-click)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.python:
        os.environ["DOCLING_PYTHON"] = str(args.python)

    root = args.root
    if root is None:
        env_root = os.environ.get("DOCLING_ROOT")
        root = Path(env_root) if env_root else Path(__file__).resolve().parent

    app = App.from_root(root)
    setup_env(app)
    ensure_dirs(app)
    app.log_file.touch()

    say("========================================")
    say(f"Docling batch parse - v{VERSION} (Python)")
    say("========================================")
    say(f"Script: {Path(__file__).resolve()}")
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
        say("  pip install docling   (v tom zhe Python chto zapuskaet skript)")
        say("  ili:")
        say("  set DOCLING_PYTHON=C:\\Users\\andrey.danilov\\AppData\\Local\\miniconda3\\python.exe")
        say("  python run_docling_parse_v2.0.6.py --python C:\\...\\miniconda3\\python.exe")
        log_append(app, "ERROR: docling not found")
        for doc in find_docling_exe_paths():
            log_append(app, f"  found docling.exe: {doc}")
        for py in iter_python_candidates():
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

    for path in iter_files(app.docs):
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
        # Double-click without args: keep window open like BAT cmd /k
        sys.argv.append("--pause")
    raise SystemExit(main())
