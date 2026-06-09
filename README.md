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

## updated_scroll_capture.exe (Windows)

Готовый EXE для склейки scroll-скриншотов (без Python):

| Файл | Описание |
|------|----------|
| `dist/updated_scroll_capture.exe` | Склейка / overlap / capture |

```bat
dist\updated_scroll_capture.exe stitch captures\ -o docs\page.png
dist\updated_scroll_capture.exe overlap frame1.png frame2.png
```

EXE пересобирается GitHub Actions при изменении `scroll_long_screenshot.py`.

## Длинный скриншот страницы (склейка)

Файл `scroll_long_screenshot.py` — надёжная склейка серии viewport-кадров с поиском
реального overlap (не фиксированные 25%).

```bat
pip install numpy Pillow playwright
playwright install chromium

python scroll_long_screenshot.py capture https://example.com -o docs/page.png
python scroll_long_screenshot.py stitch captures\ -o docs\page.png
python scroll_long_screenshot.py overlap frame1.png frame2.png
```

Склейка не зависит от диагонали/масштаба и рассчитана на **VM / VDI / RDP**:
- после каждого scroll перечитываются `scrollY`, `viewportHeight`, `devicePixelRatio`
- screenshot только после стабилизации (rAF, fonts, видимые img)
- overlap: NCC + MAD, blur, downscale — устойчивость к сжатию и gamma RDP

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
