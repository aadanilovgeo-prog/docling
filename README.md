# docling

Пакетная обработка через [Docling CLI](https://docling-project.github.io/docling/).

## Скрипт

**`run_docling_parse_v1.5.bat`** — единственный BAT в репозитории (версия **1.5**).

- Запуск через `cmd /k` — окно не закрывается сразу
- Рабочая копия в `work\` под ASCII-именем (`job_N.ext`) — без ошибок `copy` на кириллице и `(2)` в имени
- Если копия не удалась — парсинг по исходному пути (в логе: `Copy fail, direct path`)
- Все форматы Docling — [FORMATS.md](FORMATS.md)
- Выход: только **md** и **html** в `parsed\`

```bat
run_docling_parse_v1.5.bat
```

Пути: `C:\Users\andrey.danilov\Documents\VTB\docling\`

```bat
pip install docling
pip install "docling[asr]"
```
