"""Console and log output."""

from __future__ import annotations

from pathlib import Path

from docling_batch.models import App


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
