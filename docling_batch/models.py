"""Data models."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
