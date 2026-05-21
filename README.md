# docling

Утилиты для пакетной обработки документов через [Docling CLI](https://docling-project.github.io/docling/).

## Windows

`run_docling_parse.bat` — пакетный парсинг файлов из `docs` в `parsed` с логами в `logs`. Инкрементальный режим: если папка результата уже есть в `parsed` (с учётом относительного пути), файл пропускается (`[SKIP]`). Запуск: двойной щелчок или из CMD:

```bat
run_docling_parse.bat
```

Перед запуском установите Docling (`pip install docling`) и убедитесь, что `docling` доступен в `PATH`.