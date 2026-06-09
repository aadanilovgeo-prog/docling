# docling

**Версия: 3.1.3** · ветка `main`

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
pip install -r requirements.txt
python run_docling_parse_v3.1.3.py
```

Двойной щелчок по `.py` — окно останется открытым до Enter.

```bat
set DOCLING_PYTHON=%LOCALAPPDATA%\miniconda3\python.exe
python run_docling_parse_v3.1.3.py
```

## Структура

| Путь | Назначение |
|------|------------|
| `run_docling_parse_v3.1.3.py` | **Один файл** — весь скрипт |
| `DOCLING_OCR_ENGINE` | OCR-движок (по умолчанию `auto`: tesseract → easyocr → rapidocr) |
| `DOCLING_OCR_LANG` | Язык OCR (по умолчанию `rus` для кириллицы) |
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

### Русский OCR (кириллица)

Скрипт **сам выбирает** движок: Tesseract → EasyOCR → RapidOCR.

**Проще всего (рекомендуется):**
```bat
%LOCALAPPDATA%\miniconda3\python.exe -m pip install easyocr
python run_docling_parse_v3.1.3.py
```

**Или Tesseract:** [установщик](https://github.com/UB-Mannheim/tesseract/wiki) + язык **Russian**.

Ручной выбор:
```bat
set DOCLING_OCR_ENGINE=easyocr
set DOCLING_OCR_LANG=ru
```
