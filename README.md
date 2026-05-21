# docling

Утилиты для пакетной обработки документов через [Docling CLI](https://docling-project.github.io/docling/).

## Windows

Скрипты версионируются в имени файла: `run_docling_parse_v1.0.bat`, `v1.1`, …

**Текущая версия: 1.1** — `run_docling_parse_v1.1.bat`

- Выход: только **Markdown** и **HTML** в `parsed\` (без json, text, yaml)
- Изображения: `placeholder` (без отдельных файлов-артефактов)
- **PPTX/DOCX/XLSX**: без OCR с первой попытки + `--from pptx|docx|xlsx`
- **PDF**: `--pdf-backend pypdfium2`, OCR только на 1-й попытке
- Инкрементальный SKIP: если есть `parsed\<ключ>.md` и `.html`

```bat
run_docling_parse_v1.1.bat
```

Пути по умолчанию: `C:\Users\andrey.danilov\Documents\VTB\docling\` (`docs`, `parsed`, `logs`, `work`).

Перед запуском: `pip install docling`, команда `docling` в `PATH`. Для PPTX закройте файл в PowerPoint.
