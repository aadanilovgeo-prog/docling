@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  Пакетный запуск Docling CLI с инкрементальным парсингом
REM  Документация: https://docling-project.github.io/docling/
REM  Синтаксис:   docling [OPTIONS] source
REM
REM  Логика:
REM    docs\contract.pdf           -> parsed\contract\
REM    docs\contracts\2026\deal.pdf -> parsed\contracts\2026\deal\
REM  Если папка результата уже есть — файл пропускается ([SKIP]).
REM  Удалённые из docs файлы в parsed не трогаются.
REM ============================================================================

REM --- Настраиваемые пути -----------------------------------------------------
set "INPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\docs"
set "OUTPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\parsed"
set "LOG_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\logs"

REM Нормализованный путь входа (без завершающего \) для корректной подстановки
set "INPUT_NORM=%INPUT_DIR%"
if /i "%INPUT_NORM:~-1%"=="\" set "INPUT_NORM=%INPUT_NORM:~0,-1%"

REM --- Счётчики ---------------------------------------------------------------
set /a TOTAL=0
set /a PARSED_COUNT=0
set /a SKIPPED_COUNT=0
set /a ERROR_COUNT=0

REM --- Метка времени для имени лог-файла (YYYY-MM-DD_HH-MM-SS) ----------------
set "LOG_STAMP="
for /f "tokens=2 delims==" %%a in ('wmic os get LocalDateTime /value 2^>nul') do set "LOG_STAMP=%%a"
if not defined LOG_STAMP (
    echo [ERROR] Не удалось получить системную дату/время.
    exit /b 1
)
set "LOG_DATE=!LOG_STAMP:~0,4!-!LOG_STAMP:~4,2!-!LOG_STAMP:~6,2!"
set "LOG_TIME=!LOG_STAMP:~8,2!-!LOG_STAMP:~10,2!-!LOG_STAMP:~12,2!"
set "LOG_FILE=%LOG_DIR%\docling_!LOG_DATE!_!LOG_TIME!.log"

REM --- Проверка наличия Docling в PATH ----------------------------------------
where docling >nul 2>&1
if errorlevel 1 (
    echo Docling не найден. Проверь, что он установлен и добавлен в PATH.
    exit /b 1
)

REM --- Создание служебных каталогов -------------------------------------------
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- Проверка входной папки -------------------------------------------------
if not exist "%INPUT_DIR%" (
    echo [ERROR] Входная папка не найдена: "%INPUT_DIR%"
    exit /b 1
)

REM --- Заголовок лога -----------------------------------------------------------
(
    echo ============================================================
    echo Docling batch parse ^(incremental^)
    echo Started: !LOG_DATE! !LOG_TIME!
    echo Input:   "%INPUT_DIR%"
    echo Output:  "%OUTPUT_DIR%"
    echo Log:     "%LOG_FILE%"
    echo ============================================================
) >> "%LOG_FILE%"

echo.
echo Docling: инкрементальная обработка документов
echo Вход:  "%INPUT_DIR%"
echo Выход: "%OUTPUT_DIR%"
echo Лог:   "%LOG_FILE%"
echo.

REM --- Обход всех файлов во входной папке и подпапках -------------------------
for /r "%INPUT_DIR%" %%F in (*) do (
    set "FILE_EXT=%%~xF"
    if defined FILE_EXT (
        set "FILE_EXT=!FILE_EXT:~1!"
        call :IsSupportedExt "!FILE_EXT!" SUPPORTED
        if "!SUPPORTED!"=="1" (
            call :HandleOneFile "%%F"
        )
    )
)

REM --- Итоговая статистика ------------------------------------------------------
echo.
echo ============================================================
echo Total files found: !TOTAL!
echo Parsed:            !PARSED_COUNT!
echo Skipped:           !SKIPPED_COUNT!
echo Errors:            !ERROR_COUNT!
echo ============================================================
echo Лог сохранён: "%LOG_FILE%"
echo.

(
    echo.
    echo ============================================================
    echo Finished
    echo Total files found: !TOTAL!
    echo Parsed:            !PARSED_COUNT!
    echo Skipped:           !SKIPPED_COUNT!
    echo Errors:            !ERROR_COUNT!
    echo ============================================================
) >> "%LOG_FILE%"

endlocal
exit /b 0

REM ============================================================================
REM  Обработка одного файла: SKIP если результат уже есть, иначе PARSE
REM ============================================================================
:HandleOneFile
set "SRC_FILE=%~1"
set "FILE_NAME=%~nx1"

set /a TOTAL+=1

REM Вычисляем путь результата с учётом относительной структуры подпапок
call :GetOutputPath "%SRC_FILE%" FILE_OUT REL_PATH
if not defined FILE_OUT exit /b 0

REM Инкрементальная проверка: папка результата уже существует?
if exist "!FILE_OUT!\" (
    set /a SKIPPED_COUNT+=1
    echo [SKIP] !FILE_NAME!
    echo [SKIP] "%SRC_FILE%" ^-^> "!FILE_OUT!" >> "%LOG_FILE%"
    exit /b 0
)

echo [PARSE] "%SRC_FILE%" ^-^> "!FILE_OUT!" >> "%LOG_FILE%"

REM Docling создаёт каталог вывода; предварительный mkdir не нужен для логики SKIP
docling --to md --to json --to text --to html ^
    --output "!FILE_OUT!" ^
    --ocr ^
    --tables ^
    --table-mode accurate ^
    --image-export-mode referenced ^
    -v ^
    "%SRC_FILE%" >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    set /a ERROR_COUNT+=1
    echo [ERROR] !FILE_NAME!
    echo [ERROR] "%SRC_FILE%" >> "%LOG_FILE%"
    REM При ошибке удаляем пустую/неполную папку, чтобы следующий запуск повторил парсинг
    if exist "!FILE_OUT!\" rd /s /q "!FILE_OUT!" 2>nul
) else (
    set /a PARSED_COUNT+=1
    echo [PARSE] !FILE_NAME!
    echo [PARSE] done "%SRC_FILE%" >> "%LOG_FILE%"
)
exit /b 0

REM ============================================================================
REM  Вычисление пути результата по исходному файлу
REM  Аргумент 1: полный путь к исходнику
REM  Аргумент 2: имя переменной для полного пути папки результата
REM  Аргумент 3: имя переменной для относительного подпути (опционально, для лога)
REM
REM  docs\contracts\2026\deal.pdf -> parsed\contracts\2026\deal\
REM ============================================================================
:GetOutputPath
set "%~2="
set "%~3="
set "SRC_FULL=%~1"
set "SRC_DIR=%~dp1"
set "BASE_NAME=%~n1"

REM Относительный подпуть внутри docs (сохраняет вложенность и кириллицу в именах)
set "REL_PATH=!SRC_DIR:%INPUT_NORM%\=!"
if /i "!REL_PATH!"=="!SRC_DIR!" set "REL_PATH="

set "%~2=%OUTPUT_DIR%\!REL_PATH!!BASE_NAME!"
set "%~3=!REL_PATH!"
exit /b 0

REM ============================================================================
REM  Проверка расширения: поддерживается ли Docling
REM  Аргумент 1: расширение без точки
REM  Аргумент 2: имя переменной результата (1 = да, 0 = нет)
REM ============================================================================
:IsSupportedExt
set "%~2=0"
if /i "%~1"=="pdf" set "%~2=1" & exit /b 0
if /i "%~1"=="docx" set "%~2=1" & exit /b 0
if /i "%~1"=="xlsx" set "%~2=1" & exit /b 0
if /i "%~1"=="pptx" set "%~2=1" & exit /b 0
if /i "%~1"=="md" set "%~2=1" & exit /b 0
if /i "%~1"=="markdown" set "%~2=1" & exit /b 0
if /i "%~1"=="adoc" set "%~2=1" & exit /b 0
if /i "%~1"=="asciidoc" set "%~2=1" & exit /b 0
if /i "%~1"=="tex" set "%~2=1" & exit /b 0
if /i "%~1"=="html" set "%~2=1" & exit /b 0
if /i "%~1"=="htm" set "%~2=1" & exit /b 0
if /i "%~1"=="xhtml" set "%~2=1" & exit /b 0
if /i "%~1"=="csv" set "%~2=1" & exit /b 0
if /i "%~1"=="png" set "%~2=1" & exit /b 0
if /i "%~1"=="jpg" set "%~2=1" & exit /b 0
if /i "%~1"=="jpeg" set "%~2=1" & exit /b 0
if /i "%~1"=="tif" set "%~2=1" & exit /b 0
if /i "%~1"=="tiff" set "%~2=1" & exit /b 0
if /i "%~1"=="bmp" set "%~2=1" & exit /b 0
if /i "%~1"=="webp" set "%~2=1" & exit /b 0
if /i "%~1"=="wav" set "%~2=1" & exit /b 0
if /i "%~1"=="mp3" set "%~2=1" & exit /b 0
if /i "%~1"=="m4a" set "%~2=1" & exit /b 0
if /i "%~1"=="aac" set "%~2=1" & exit /b 0
if /i "%~1"=="ogg" set "%~2=1" & exit /b 0
if /i "%~1"=="flac" set "%~2=1" & exit /b 0
if /i "%~1"=="mp4" set "%~2=1" & exit /b 0
if /i "%~1"=="avi" set "%~2=1" & exit /b 0
if /i "%~1"=="mov" set "%~2=1" & exit /b 0
if /i "%~1"=="vtt" set "%~2=1" & exit /b 0
if /i "%~1"=="json" set "%~2=1" & exit /b 0
if /i "%~1"=="xml" set "%~2=1" & exit /b 0
exit /b 0
