# docling

**Версия: 3.0.0** · ветка `main`

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
pip install -r requirements.txt
python run_docling_parse_v3.0.0.py
```

Двойной щелчок по `.py` — окно останется открытым до Enter.

```bat
set DOCLING_PYTHON=%LOCALAPPDATA%\miniconda3\python.exe
python run_docling_parse_v3.0.0.py
```

## Структура

| Путь | Назначение |
|------|------------|
| `run_docling_parse_v3.0.0.py` | **Один файл** — весь скрипт |
| `_docling_runner.py` | Вспомогательный (PILLOW для subprocess) |
| `docs/` | Вход |
| `parsed/` | `.md` + `.html` |
| `logs/` | Логи |
| `work/` | Рабочие копии и тайлы |

Форматы: [FORMATS.md](FORMATS.md)

## Поведение

- Scroll-скриншоты — нарезка по высоте, прогресс `tile 1/30`
- Пустой вывод = ошибка, перепарсинг
- 3 попытки; PDF — OCR только на 1-й

## Docling

```bat
pip install docling
pip install "docling[asr]"
```
