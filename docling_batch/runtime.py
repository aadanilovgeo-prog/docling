"""Locate Python interpreter with docling installed."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from docling_batch.models import DoclingRuntime

_runtime: DoclingRuntime | None = None


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

    home = Path.home()
    for rel in (
        "AppData/Local/miniconda3",
        "AppData/Local/Programs/miniconda3",
        "AppData/Local/anaconda3",
        "miniconda3",
        "Anaconda3",
    ):
        add(home / rel)

    if cp := os.environ.get("CONDA_PREFIX"):
        add(Path(cp))

    return tuple(roots)


def augment_conda_path() -> None:
    extra: list[str] = []
    for root in _conda_roots():
        extra.append(str(root))
        scripts = root / "Scripts"
        if scripts.is_dir():
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
            capture_output=True,
            timeout=120,
            creationflags=_subprocess_flags(),
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


def _make_runtime(py: Path) -> DoclingRuntime:
    if py.resolve() == Path(sys.executable).resolve():
        return DoclingRuntime("inprocess", py, f"in-process ({py})")
    return DoclingRuntime("subprocess", py, f"subprocess ({py})")


def resolve_docling_runtime() -> DoclingRuntime | None:
    global _runtime
    if _runtime is not None:
        return _runtime

    augment_conda_path()
    trusted = {
        py.resolve()
        for doc in _docling_exe_paths()
        if (py := _python_for_docling_exe(doc))
    }

    for py in _iter_python_candidates():
        if py.resolve() in trusted or _python_has_docling(py):
            _runtime = _make_runtime(py)
            return _runtime
    return None


def docling_runner_path() -> Path:
    return Path(__file__).resolve().parent.parent / "_docling_runner.py"


def find_docling_exe_paths() -> list[Path]:
    return list(_docling_exe_paths())


def iter_python_candidates() -> list[Path]:
    return _iter_python_candidates()
