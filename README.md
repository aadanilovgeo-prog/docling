# docling

Утилиты для пакетной обработки документов через [Docling CLI](https://docling-project.github.io/docling/).

## Windows

Скрипты версионируются в имени файла: `run_docling_parse_v1.0.bat`, далее `v1.1`, `v2.0` и т.д.

**Текущая версия: 1.0** — `run_docling_parse_v1.0.bat`

Пакетный парсинг файлов из `docs` в `parsed` с логами в `logs`. Скрипт можно запускать из любой папки: пути к данным заданы абсолютными (по умолчанию `C:\Users\andrey.danilov\Documents\VTB\docling\`). Результаты сохраняются **напрямую в `parsed\`** (без подпапок). Инкрементальный режим: если уже есть `parsed\<ключ>.md` и `.json`, файл пропускается (`[SKIP]`).

```bat
run_docling_parse_v1.0.bat
```

Перед запуском установите Docling (`pip install docling`) и убедитесь, что `docling` доступен в `PATH`.

На Windows при кириллице в именах PDF скрипт копирует файл в `work\`, задаёт отдельный `TEMP` в `work\tmp` и для PDF использует `--pdf-backend pypdfium2`. При ошибке — 3 попытки (1 + 2 повтора); повторы 2–3 идут с `--no-ocr`, если не удаётся загрузить модели OCR.
