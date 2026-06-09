"""CLI entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from docling_batch.config import VERSION, pillow_limit
from docling_batch.io import ensure_dirs, log_append, say
from docling_batch.models import App
from docling_batch.pillow_util import apply_pillow_limit
from docling_batch.processor import handle_file
from docling_batch.runtime import find_docling_exe_paths, iter_python_candidates, resolve_docling_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Docling batch parse v{VERSION}: docs/ -> parsed/ (md + html)",
    )
    parser.add_argument("--root", type=Path, default=None, help="Project root")
    parser.add_argument("--python", type=Path, default=None, help="Python with docling")
    parser.add_argument("--pause", action="store_true", help="Wait for Enter before exit")
    return parser.parse_args()


def setup_env(app: App) -> None:
    apply_pillow_limit()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["TEMP"] = str(app.tmp)
    os.environ["TMP"] = str(app.tmp)


def _print_header(app: App) -> None:
    say("========================================")
    say(f"Docling batch parse - v{VERSION} (Python)")
    say("========================================")
    say(f"Script: {Path(__file__).resolve().parent.parent / 'run_docling_parse_v3.0.0.py'}")
    say(f"Root:   {app.root}")
    say("Vyhod:  md + html")
    say("========================================")
    say("Proverka papok...")
    say("  docs, parsed, logs, work - OK")
    say("")


def _print_summary(app: App) -> int:
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
    return 1 if app.stats.errors else 0


def main() -> int:
    args = parse_args()

    if args.python:
        os.environ["DOCLING_PYTHON"] = str(args.python)

    if args.root is not None:
        root = args.root
    elif env_root := os.environ.get("DOCLING_ROOT"):
        root = Path(env_root)
    else:
        root = Path(__file__).resolve().parent.parent

    app = App.from_root(root)
    setup_env(app)
    ensure_dirs(app)
    app.log_file.touch()

    _print_header(app)
    log_append(app, f"Started v{VERSION}")
    log_append(app, f"PILLOW_MAX_IMAGE_PIXELS={pillow_limit()}")
    log_append(app, f"Script Python: {sys.executable}")

    runtime = resolve_docling_runtime()
    if runtime is None:
        say("OSHIBKA: docling ne naiden.")
        say("  pip install docling")
        say("  set DOCLING_PYTHON=%LOCALAPPDATA%\\miniconda3\\python.exe")
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

    for path in sorted(app.docs.rglob("*")):
        if path.is_file():
            handle_file(app, path)

    code = _print_summary(app)
    if args.pause:
        say("")
        input("Gotovo. Nazhmite Enter...")
    return code


def cli() -> None:
    if sys.platform == "win32" and len(sys.argv) == 1:
        sys.argv.append("--pause")
    raise SystemExit(main())
