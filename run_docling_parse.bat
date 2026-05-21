@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  Пакетный запуск Docling CLI для конвертации документов
REM  Документация: https://docling-project.github.io/docling/
REM  Синтаксис:   docling [OPTIONS] source
REM ============================================================================

REM --- Настраиваемые пути -----------------------------------------------------
set "INPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\docs"
set "OUTPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\parsed"
set "LOG_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\logs"

REM --- Счётчики обработки -----------------------------------------------------
set /a TOTAL=0
set /a OK_COUNT=0
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
    echo Docling batch parse
    echo Started: !LOG_DATE! !LOG_TIME!
    echo Input:   "%INPUT_DIR%"
    echo Output:  "%OUTPUT_DIR%"
    echo Log:     "%LOG_FILE%"
    echo ============================================================
) >> "%LOG_FILE%"

echo.
echo Docling: пакетная обработка документов
echo Вход:  "%INPUT_DIR%"
echo Выход: "%OUTPUT_DIR%"
echo Лог:   "%LOG_FILE%"
echo.

REM --- Обход всех файлов во входной папке и подпапках -------------------------
for /r "%INPUT_DIR%" %%F in (*) do (
    set "FULL_PATH=%%F"
    set "FILE_EXT=%%~xF"
    if defined FILE_EXT (
        set "FILE_EXT=!FILE_EXT:~1!"
        call :IsSupportedExt "!FILE_EXT!" SUPPORTED
        if "!SUPPORTED!"=="1" (
            call :ProcessOneFile "%%F"
        )
    )
)

REM --- Итоговая статистика ------------------------------------------------------
echo.
echo ============================================================
echo Обработано файлов: !TOTAL!
echo Успешно:           !OK_COUNT!
echo С ошибками:        !ERROR_COUNT!
echo ============================================================
echo Лог сохранён: "%LOG_FILE%"
echo.

(
    echo.
    echo ============================================================
    echo Finished
    echo Total:  !TOTAL!
    echo OK:     !OK_COUNT!
    echo Errors: !ERROR_COUNT!
    echo ============================================================
) >> "%LOG_FILE%"

endlocal
exit /b 0

REM ============================================================================
REM  Обработка одного файла через Docling CLI
REM ============================================================================
:ProcessOneFile
set "SRC_FILE=%~1"
set /a TOTAL+=1

REM Подпапка результата повторяет структуру входа относительно INPUT_DIR
set "REL_SUBDIR=%~dp1"
set "REL_SUBDIR=!REL_SUBDIR:%INPUT_DIR%\=!"
if /i "!REL_SUBDIR!"=="%INPUT_DIR%\" set "REL_SUBDIR="
set "FILE_OUT=%OUTPUT_DIR%\!REL_SUBDIR!%~n1"
if not exist "!FILE_OUT!" (
    REM mkdir создаёт всю цепочку подпапок (актуально для вложенных docs\sub\...)
    mkdir "!FILE_OUT!" 2>nul
)

echo [!TOTAL!] Обработка: "%SRC_FILE%"
echo [!TOTAL!] "%SRC_FILE%" >> "%LOG_FILE%"

REM Один вызов CLI с несколькими форматами экспорта (см. --to в справке Docling)
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
    echo [ERROR] "%SRC_FILE%"
    echo [ERROR] "%SRC_FILE%" >> "%LOG_FILE%"
) else (
    set /a OK_COUNT+=1
    echo [OK] "%SRC_FILE%"
    echo [OK] "%SRC_FILE%" >> "%LOG_FILE%"
)
exit /b 0

REM ============================================================================
REM  Проверка расширения: поддерживается ли Docling
REM  Второй аргумент — имя переменной результата (1/0)
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
