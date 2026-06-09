"""Input format → docling CLI options."""

from __future__ import annotations

from docling_batch.models import FormatSpec

_TABLES = ["--tables", "--table-mode", "accurate"]
_ASR = ["--pipeline", "asr", "--asr-model", "whisper_tiny"]

_FORMATS: dict[str, FormatSpec] = {
    "pdf": FormatSpec(
        kind="pdf",
        from_arg=["--from", "pdf"],
        pdf=["--pdf-backend", "pypdfium2"],
        tables=_TABLES,
        ocr_first=True,
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
