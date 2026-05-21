# docling

Утилиты для пакетной обработки документов через [Docling CLI](https://docling-project.github.io/docling/).

## Windows

`run_docling_parse.bat` — пакетный парсинг файлов из `docs` в `parsed` с логами в `logs`. Скрипт можно запускать из любой папки: пути к данным заданы абсолютными (по умолчанию `C:\Users\andrey.danilov\Documents\VTB\docling\`). Инкрементальный режим: если папка результата уже есть в `parsed` (с учётом относительного пути), файл пропускается (`[SKIP]`). Запуск: двойной щелчок или из CMD:

```bat
run_docling_parse.bat
```

Перед запуском установите Docling (`pip install docling`) и убедитесь, что `docling` доступен в `PATH`.

На Windows при кириллице в именах PDF скрипт копирует файл в `work\` с ASCII-именем, задаёт отдельный `TEMP` в `work\tmp` и для PDF использует `--pdf-backend pypdfium2` (обход [docling-parse#116](https://github.com/docling-project/docling-parse/issues/116)). При `WinError 32` выполняются до 3 повторов с паузой 5 с — закройте PDF в просмотрщике и при необходимости добавьте папку `docling` в исключения антивируса.