#!/usr/bin/env python3
"""
Docling batch parser v2.0 — Python port of run_docling_parse_v1.5.bat (v1.6 logic).

docs/  ->  parsed/  (.md + .html)
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

VERSION = "2.0.0"
DEFAULT_PILLOW = "9999999999"
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


def find_docling_cmd() -> list[str]:
    exe = shutil.which("docling")
    if exe:
        return [exe]
    return [sys.executable, "-m", "docling"]


def build_docling_cmd(
    base: list[str],
    app: App,
    src: Path,
    spec: FormatSpec,
    use_ocr: bool,
) -> list[str]:
    cmd = [
        *base,
        "--to", "md",
        "--to", "html",
        "--output", str(app.parsed),
        *spec.from_arg,
        *spec.pipeline,
        *spec.pdf,
        "--ocr" if use_ocr else "--no-ocr",
        *spec.tables,
        "--image-export-mode", "placeholder",
        "-v", str(src),
    ]
    return cmd


def run_docling(cmd: list[str], app: App) -> int:
    log_append(app, "CMD " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    with app.log_file.open("a", encoding="utf-8") as lf:
        proc = subprocess.run(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(app.root),
            env=os.environ.copy(),
        )
    log_append(app, f"EXIT {proc.returncode}")
    return proc.returncode


def run_with_retry(app: App, src: Path, job_id: str, out_key: str, ext: str) -> bool:
    spec = resolve_format(ext)
    if spec.kind == "unknown":
        return False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        cleanup_artifacts(app.parsed, job_id)
        cleanup_artifacts(app.parsed, out_key)

        use_ocr = spec.ocr_first
        if attempt >= 2 and spec.kind in ("pdf", "image"):
            use_ocr = False

        log_append(
            app,
            f"Attempt {attempt}/{MAX_ATTEMPTS} {spec.kind} job={job_id} out={out_key} ocr={'yes' if use_ocr else 'no'}",
        )
        ocr_tag = ", OCR" if use_ocr else ""
        say(f"  -> attempt {attempt}/{MAX_ATTEMPTS} ({spec.kind}{ocr_tag})")

        code = run_docling(build_docling_cmd(find_docling_cmd(), app, src, spec, use_ocr), app)
        if code == 0:
            if output_complete(app.parsed, job_id):
                rename_job_outputs(app.parsed, job_id, out_key)
                if output_complete(app.parsed, out_key):
                    remove_unwanted(app.parsed, job_id)
                    remove_unwanted(app.parsed, out_key)
                    return True
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

    if output_complete(app.parsed, key):
        app.stats.skipped += 1
        say(f"[SKIP] {src.name}")
        log_append(app, f"[SKIP] {src}")
        return

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
    os.environ.setdefault("PILLOW_MAX_IMAGE_PIXELS", DEFAULT_PILLOW)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["TEMP"] = str(app.tmp)
    os.environ["TMP"] = str(app.tmp)


def check_docling() -> bool:
    if shutil.which("docling"):
        return True
    try:
        import docling  # noqa: F401
        return True
    except ImportError:
        return False


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
        "--pause",
        action="store_true",
        help="Wait for Enter before exit (Windows double-click)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

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
    log_append(app, f"PILLOW_MAX_IMAGE_PIXELS={os.environ.get('PILLOW_MAX_IMAGE_PIXELS', DEFAULT_PILLOW)}")

    if not check_docling():
        say("OSHIBKA: docling ne ustanovlen. pip install docling")
        log_append(app, "ERROR: docling not found")
        if args.pause:
            input("Enter...")
        return 1

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
