# docling

**Версия: 2.0.8** · ветка `main`

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
pip install -r requirements.txt
python run_docling_parse_v2.0.8.py
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
| `DOCLING_PILLOW_MAX_PIXELS` | Лимит Pillow (приоритетнее `PILLOW_MAX_IMAGE_PIXELS`) |
| `DOCLING_OCR_MAX_SIDE` | Макс. сторона изображения для OCR (по умолчанию `8192`) |

Скрипт ищет `miniconda3\python.exe` рядом с `Scripts\docling.exe` и запускает `_docling_runner.py` (не `docling.exe` — иначе PILLOW не работает).

Если docling установлен в miniconda, а скрипт запускается другим Python:

```bat
set DOCLING_PYTHON=%LOCALAPPDATA%\miniconda3\python.exe
python run_docling_parse_v2.0.8.py
```

По умолчанию **ROOT** = папка со скриптом.

---

## Структура папок

| Папка | Назначение |
|-------|------------|
| `docs` | Вход, рекурсивно |
| `parsed` | `.md` + `.html` |
| `logs` | Логи |
| `work` | Рабочие копии (`job_*`) |

Форматы: [FORMATS.md](FORMATS.md)

## Поведение (v2.0.8)

- Рекурсивный обход `docs\`
- Пропуск готовых пар `.md` + `.html` **с непустым содержимым**
- 3 попытки; для PDF — OCR только на 1-й
- Длинные scroll-скриншоты — **нарезка по высоте** (ширина сохраняется), не сжатие в «полоску»
- Обычные большие фото — уменьшение перед OCR (8192 → 4096 → 2048 px)
- Пустой вывод считается ошибкой (перепарсинг)
- Work copy в `work\job_<N>_<random>.ext`
- Лог: `logs\docling_YYYYMMDD_HHMMSS_*.log`

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH. Закройте файлы в Office перед парсингом.
