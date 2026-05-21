# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Актуальный скрипт

**`run_docling_parse_v1.3.bat`** — все форматы из [справки Docling](https://docling-project.github.io/docling/usage/supported_formats/), выход только **md + html**.

Подробная таблица: [FORMATS.md](FORMATS.md)

```bat
run_docling_parse_v1.3.bat
```

Пути (можно менять в BAT): `C:\Users\andrey.danilov\Documents\VTB\docling\`

| Папка | Назначение |
|-------|------------|
| `docs` | Входные файлы |
| `parsed` | Результаты `.md` и `.html` |
| `logs` | Логи запуска |
| `work` | Временные копии |

## Установка

```bat
pip install docling
pip install "docling[asr]"
```

Для **mp4/avi/mov** нужен **ffmpeg** в PATH. Для **pptx/docx/xlsx** закройте файл в Office перед запуском.

## Версии BAT

| Файл | Версия |
|------|--------|
| `run_docling_parse_v1.3.bat` | **текущий** |
| `run_docling_parse_v1.2.bat` | все форматы, md+html |
| `run_docling_parse_v1.1.bat` | pptx fix |
| `run_docling_parse_v1.0.bat` | устарел |
