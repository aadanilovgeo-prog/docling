# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Две независимые реализации

| Реализация | Файл | Запуск |
|------------|------|--------|
| **BAT v1.5** | `run_docling_parse_v1.5.bat` | Двойной щелчок (свой `cmd /k`) |
| **C v2.0** | `run_docling_parse.exe` | Двойной щелчок **без BAT** |

Обе делают одно и то же: `docs\` → `parsed\` (только md + html). Можно пользоваться **любой одной**.

---

## C: `run_docling_parse.exe` (автономный)

**Не требует BAT.** Скачайте готовый exe или соберите сами.

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

- Сам открывает консоль, задаёт заголовок окна
- В конце ждёт **Enter** (окно не исчезает)
- `--no-pause` или `DOCLING_NO_PAUSE=1` — для скриптов/планировщика
- **ROOT** по умолчанию = **папка, где лежит exe** (рядом должны быть `docs\`, создаются `parsed\`, `logs\`, `work\`)
- Переопределение: `set DOCLING_ROOT=C:\path\to\docling`

### Оптимизации (только C)

- Потоковый лог (растёт во время работы Docling)
- Прогресс пакета `[ 33%] 2/6`
- `--document-timeout` 7200 с (`DOCLING_TIMEOUT`, `0` = без лимита)
- Unicode `CopyFileW`, work copy `job_*`

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
| `work` | Копии + `tmp` (TEMP) |

Форматы: [FORMATS.md](FORMATS.md)

## Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для видео — **ffmpeg** в PATH. Закройте файлы в Office перед парсингом.
