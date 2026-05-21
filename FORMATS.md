# Podderzhivaemye formaty (run_docling_parse_v1.3.bat)

| Gruppa | Rasshireniya | Docling `--from` | Osobennosti |
|--------|-------------|------------------|-------------|
| PDF | pdf | pdf | pypdfium2, OCR na 1-j popytke |
| Office | docx, xlsx, pptx | docx / xlsx / pptx | bez OCR, tablicy |
| Tekst | md, markdown, adoc, asciidoc, tex, html, htm, xhtml, csv, vtt | md / asciidoc / latex / html / csv / vtt | bez OCR |
| Izobrazheniya | png, jpg, jpeg, tif, tiff, bmp, webp | image | OCR na 1-j popytke |
| Audio | wav, mp3, m4a, aac, ogg, flac | audio | `--pipeline asr` |
| Video | mp4, avi, mov | audio + ASR | nuzhen ffmpeg |
| JSON | json | json_docling | |
| XML | xml | auto | uspto / jats / xbrl |

**Vyhod:** tolko `parsed\<klyuch>.md` i `parsed\<klyuch>.html`

## Dopolnitelno ustanovit

```bat
pip install docling
pip install "docling[asr]"
```

Video: ustanovite [ffmpeg](https://ffmpeg.org/) v PATH.
