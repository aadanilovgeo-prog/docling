"""Output paths, validation, cleanup."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from docling_batch.config import MIN_OUTPUT_CHARS, OUTPUT_SUFFIXES


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
            "<!DOCTYPE html>\n<html><body></body></html>",
            encoding="utf-8",
        )

    for stem in stems:
        if stem != out_key:
            cleanup_artifacts(parsed, stem)

    return output_valid(parsed, out_key)
