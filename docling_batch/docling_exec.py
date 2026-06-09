"""Invoke docling CLI in-process or via subprocess."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from docling_batch.config import CONVERSION_FAILURE_MARKERS, pillow_limit
from docling_batch.io import log_append, log_cmd, write_log_output
from docling_batch.models import App, DoclingRuntime, FormatSpec
from docling_batch.pillow_util import apply_pillow_limit
from docling_batch.runtime import (
    _subprocess_flags,
    docling_runner_path,
    resolve_docling_runtime,
)


def build_docling_args(app: App, src: Path, spec: FormatSpec, use_ocr: bool) -> list[str]:
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


def _run_inprocess(args: list[str], app: App) -> tuple[int, str]:
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

    output = buf.getvalue()
    write_log_output(app, output)
    return code, output


def _run_subprocess(runtime: DoclingRuntime, args: list[str], app: App) -> tuple[int, str]:
    cmd = [str(runtime.python), "-u", str(docling_runner_path()), *args]
    log_cmd(app, cmd)
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
        code, out = _run_inprocess(args, app)
        log_append(app, f"EXIT {code}")
        return code, out
    return _run_subprocess(runtime, args, app)
