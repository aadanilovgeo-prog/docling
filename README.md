# docling

Пакетная обработка через [Docling CLI](https://docling-project.github.io/docling/).

## Скрипт

**`run_docling_parse_v1.4.bat`** — единственный BAT в репозитории (версия **1.4**).

- Запуск через `cmd /k` — окно не закрывается сразу
- Все форматы Docling — [FORMATS.md](FORMATS.md)
- Выход: только **md** и **html** в `parsed\`

```bat
run_docling_parse_v1.4.bat
```

Пути: `C:\Users\andrey.danilov\Documents\VTB\docling\`

```bat
pip install docling
pip install "docling[asr]"
```
