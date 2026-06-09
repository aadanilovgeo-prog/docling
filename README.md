# docling

**Версия: 2.0.1** · ветка `main`

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Запуск

```bat
pip install -r requirements.txt
python run_docling_parse_v2.0.1.py
```

Двойной щелчок по `.py` (если Python ассоциирован с файлами) — окно останется открытым до Enter.

### Параметры

| Параметр / переменная | Назначение |
|-----------------------|------------|
| `--root PATH` | Корень проекта (папки `docs`, `parsed`, …) |
| `DOCLING_ROOT` | То же через env |
| `--pause` | Ждать Enter в конце |
| `PILLOW_MAX_IMAGE_PIXELS` | Лимит Pillow для больших PNG (по умолчанию `9999999999`) |
| `DOCLING_PILLOW_MAX_PIXELS` | То же (приоритетнее) |

Docling запускается как `python -m docling` (тот же интерпретатор), чтобы `PILLOW` доходил до Pillow.

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

## Поведение (v2.0.1)

- Рекурсивный обход `docs\`
- Пропуск готовых пар `.md` + `.html`
- 3 попытки, OCR на 1-й для PDF/изображений
- Work copy в `work\job_<N>_<random>.ext`
- Лог: `logs\docling_YYYYMMDD_HHMMSS_*.log`

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH. Закройте файлы в Office перед парсингом.
