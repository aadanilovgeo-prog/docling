# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Две независимые реализации

| Реализация | Файл | Запуск |
|------------|------|--------|
| **BAT v1.5** | `run_docling_parse_v1.5.bat` | Двойной щелчок (свой `cmd /k`) |
| **C v3.0** | `run_docling_parse.exe` | Двойной щелчок **без BAT** |

Обе делают одно: `docs\` → `parsed\` (md + html). BAT — полный CMD-скрипт; exe — минимальный лаунчер.

---

## C: `run_docling_parse.exe` (v3.0)

Минимальный батч-раннер: сканирует `docs\`, вызывает `python -m docling`, пишет `.md` + `.html` в `parsed\`.

### Скачать (всегда актуальная сборка с main)

| Способ | Ссылка |
|--------|--------|
| **Файл в репозитории** | [dist/run_docling_parse.exe](dist/run_docling_parse.exe) |
| **Прямая ссылка** | https://github.com/aadanilovgeo-prog/docling/raw/main/dist/run_docling_parse.exe |
| **Release** | https://github.com/aadanilovgeo-prog/docling/releases/tag/latest-build |

Сборка на каждый push в `main` (изменения `src/`): GitHub Actions → [Build Windows EXE](.github/workflows/build-exe.yml).

### Собрать локально

```bat
build.bat
```

MSVC `cl` или MinGW `gcc` (см. `build.bat`).

### Поведение exe

- **ROOT** = папка exe (или `DOCLING_ROOT`)
- Создаёт `docs\`, `parsed\`, `logs\` при старте
- Запускает `python.exe -m docling` (или `DOCLING_PYTHON`)
- Пропускает файлы, у которых уже есть `.md` + `.html`
- Лог: `logs\run_YYYYMMDD_HHMMSS.log` (включая stdout/stderr docling)
- `PILLOW_MAX_IMAGE_PIXELS=9999999999` для больших PNG
- `DOCLING_TIMEOUT` — таймаут документа в секундах (по умолчанию 7200)

Исходник: `src/run_docling_parse.c`

---

## BAT: `run_docling_parse_v1.5.bat`

Классический CMD-скрипт, пути зашиты в файле:

`C:\Users\andrey.danilov\Documents\VTB\docling\`

```bat
run_docling_parse_v1.5.bat
```

---

## Структура папок

| Папка | Назначение |
|-------|------------|
| `docs` | Вход, рекурсивно |
| `parsed` | `.md` + `.html` |
| `logs` | Логи |

Форматы: [FORMATS.md](FORMATS.md)

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH. Закройте файлы в Office перед парсингом.
