# docling

Пакетная обработка документов через [Docling CLI](https://docling-project.github.io/docling/).

## Актуальное решение (v2.0, C)

| Файл | Назначение |
|------|------------|
| **`run_docling_parse.exe`** | Основная программа (после сборки) |
| **`run_docling_parse.bat`** | Запуск через `cmd /k` — окно не закрывается |
| **`build.bat`** | Сборка EXE (MSVC `cl` или MinGW `gcc`) |
| **`src/run_docling_parse.c`** | Исходный код |

Эквивалент функциональности **BAT v1.5**, плюс оптимизации:

- Нативный Unicode (`CopyFileW`) — кириллица и `(2)` в именах
- Рабочая копия `work\job_<N>_<random>.ext` + переименование в `OUT_KEY`
- Fallback на исходный путь при ошибке копирования
- **Потоковый лог** — строки пишутся в файл по мере работы Docling
- **Прогресс пакета** — `[ 33%] 2/6` перед каждым файлом
- **`--document-timeout`** (по умолчанию 7200 с) — защита от бесконечного зависания OCR
- Двухфазное сканирование: сначала список файлов, потом обработка

### Быстрый старт (Windows)

```bat
build.bat
run_docling_parse.bat
```

Пути по умолчанию: `C:\Users\andrey.danilov\Documents\VTB\docling\`

| Папка | Назначение |
|-------|------------|
| `docs` | Вход, рекурсивно |
| `parsed` | Только `.md` и `.html` (плоско) |
| `logs` | Логи |
| `work` | Копии + `tmp` (TEMP/TMP) |

### Переменные окружения

| Переменная | Описание |
|------------|----------|
| `DOCLING_ROOT` | Корень вместо пути по умолчанию |
| `DOCLING_TIMEOUT` | Таймаут на документ в секундах (`0` = без лимита) |

Форматы: [FORMATS.md](FORMATS.md)

## Установка Docling

```bat
pip install docling
pip install "docling[asr]"
```

Для **mp4/avi/mov** — **ffmpeg** в PATH. Перед парсингом закройте файлы в Office.
