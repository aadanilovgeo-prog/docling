# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
run_docling_parse_v1.5.bat
```

Двойной щелчок — откроется окно `cmd`. Скрипт обрабатывает `docs\` → `parsed\` (только `.md` + `.html`).

Пути по умолчанию зашиты в BAT:

`C:\Users\andrey.danilov\Documents\VTB\docling\`

---

## Структура папок

| Папка | Назначение |
|-------|------------|
| `docs` | Вход, рекурсивно |
| `parsed` | `.md` + `.html` |
| `logs` | Логи |
| `work` | Рабочие копии файлов |

Форматы: [FORMATS.md](FORMATS.md)

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH. Закройте файлы в Office перед парсингом.
