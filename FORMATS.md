# Поддерживаемые форматы (BAT v1.5 / C exe v3.0)

| Gruppa | Rasshireniya | Docling `--from` | Osobennosti |
|--------|-------------|------------------|-------------|
| PDF | pdf | pdf | pypdfium2, OCR na 1-j popytke |
| Office | docx, xlsx, pptx | docx / xlsx / pptx | bez OCR, tablicy |
| Tekst | md, markdown, adoc, asciidoc, tex, html, htm, xhtml, csv, vtt | md / asciidoc / latex / html / csv / vtt | bez OCR |
| Izobrazheniya | png, jpg, jpeg, tif, tiff, bmp, webp | image | bez --ocr (bystree) |
| Audio | wav, mp3, m4a, aac, ogg, flac | audio | `--pipeline asr` |
| Video | mp4, avi, mov | audio + ASR | nuzhen ffmpeg |
| JSON | json | json_docling | |
| XML | xml | auto | uspto / jats / xbrl |

**Vyhod:** tolko `parsed\<klyuch>.md` i `parsed\<klyuch>.html`

**OUT_KEY:** `docs\file.pdf` → `file`; `docs\sub\file.pdf` → `sub_file`

**C v3.0:** obrabotka napryamuyu iz `docs\`, bez work copy.

## Dopolnitelno

```bat
pip install docling
pip install "docling[asr]"
```

C: `build.bat` → `run_docling_parse.exe` (запуск без BAT).
