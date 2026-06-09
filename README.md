# docling

**Версия: 3.0.0** · ветка `main`

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
pip install -r requirements.txt
python run_docling_parse_v3.0.0.py
```

Двойной щелчок по `.py` (если Python ассоциирован с файлами) — окно останется открытым до Enter.

### Параметры

| Параметр / переменная | Назначение |
|-----------------------|------------|
| `--root PATH` | Корень проекта (папки `docs`, `parsed`, …) |
| `DOCLING_ROOT` | То же через env |
| `--pause` | Ждать Enter в конце |
| `PILLOW_MAX_IMAGE_PIXELS` | Лимит Pillow для больших PNG (по умолчанию `9999999999`) |
| `DOCLING_PYTHON` | Python с docling (напр. `...\miniconda3\python.exe`) |
| `--python PATH` | То же через аргумент |
| `DOCLING_OCR_MAX_SIDE` | Макс. высота/ширина фрагмента OCR (по умолчанию `8192`) |

Скрипт ищет `miniconda3\python.exe` и запускает `_docling_runner.py` (не `docling.exe`).

```bat
set DOCLING_PYTHON=%LOCALAPPDATA%\miniconda3\python.exe
python run_docling_parse_v3.0.0.py
```

## Структура проекта

| Путь | Назначение |
|------|------------|
| `run_docling_parse_v3.0.0.py` | Точка входа |
| `docling_batch/` | Модули парсера |
| `docs/` | Входные файлы |
| `parsed/` | `.md` + `.html` |
| `logs/` | Логи |
| `work/` | Рабочие копии и тайлы |

Форматы: [FORMATS.md](FORMATS.md)

## Поведение (v3.0.0)

- Рекурсивный обход `docs\`
- Пропуск готовых пар `.md` + `.html` с непустым содержимым
- Длинные scroll-скриншоты — нарезка по высоте (ширина сохраняется)
- 3 попытки; для PDF — OCR только на 1-й
- Прогресс тайлов в консоли: `tile 1/30`

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH.
