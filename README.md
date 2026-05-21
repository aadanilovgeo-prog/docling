# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Скрипт

**`run_docling_parse_v1.3.bat`** — единственный BAT-файл в репозитории.

- Все форматы Docling — см. [FORMATS.md](FORMATS.md)
- Выход: только **md** и **html** в `parsed\`
- Полный отчёт в консоли и логе

```bat
run_docling_parse_v1.3.bat
```

Пути: `C:\Users\andrey.danilov\Documents\VTB\docling\` (`docs`, `parsed`, `logs`, `work`)

## Установка

```bat
pip install docling
pip install "docling[asr]"
```

Для видео нужен **ffmpeg**. Перед запуском закройте файлы в Office.
