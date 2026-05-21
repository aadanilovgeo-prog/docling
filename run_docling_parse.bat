@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  Пакетный запуск Docling CLI с инкрементальным парсингом
REM  Документация: https://docling-project.github.io/docling/
REM
REM  Обход WinError 32 / кириллицы в именах (см. docling-parse #116):
REM    - копия исходника в ASCII-имя в папке work\
REM    - отдельный TEMP без кириллицы
REM    - для PDF: --pdf-backend pypdfium2
REM    - повторные попытки при блокировке файла
REM ============================================================================

REM --- Кодировка консоли и Python (кириллица в путях docs\) -------------------
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM --- Настраиваемые пути -----------------------------------------------------
set "INPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\docs"
set "OUTPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\parsed"
set "LOG_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\logs"
set "WORK_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\work"
set "TMP_DIR=%WORK_DIR%\tmp"

REM Нормализованный путь входа (без завершающего \)
set "INPUT_NORM=%INPUT_DIR%"
if /i "%INPUT_NORM:~-1%"=="\" set "INPUT_NORM=%INPUT_NORM:~0,-1%"

REM --- Счётчики ---------------------------------------------------------------
set /a TOTAL=0
set /a PARSED_COUNT=0
set /a SKIPPED_COUNT=0
set /a ERROR_COUNT=0
set /a MAX_RETRIES=3
set /a RETRY_DELAY_SEC=5

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
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

REM Docling/Python пишут временные файлы сюда (только ASCII в пути)
set "TEMP=%TMP_DIR%"
set "TMP=%TMP_DIR%"

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
    echo Work:    "%WORK_DIR%"
    echo Temp:    "%TMP_DIR%"
    echo Log:     "%LOG_FILE%"
    echo ============================================================
) >> "%LOG_FILE%"

echo.
echo Docling: инкрементальная обработка документов
echo Вход:  "%INPUT_DIR%"
echo Выход: "%OUTPUT_DIR%"
echo Work:  "%WORK_DIR%"
echo Лог:   "%LOG_FILE%"
echo.

REM --- Обход всех файлов во входной папке и подпапках -------------------------
for /r "%INPUT_DIR%" %%F in (*) do (
    REM Пропуск временных/блокировочных файлов Office (~$...)
    set "BASE_ONLY=%%~nxF"
    if not "!BASE_ONLY:~0,2!"=="~$" (
        set "FILE_EXT=%%~xF"
        if defined FILE_EXT (
            set "FILE_EXT=!FILE_EXT:~1!"
            call :IsSupportedExt "!FILE_EXT!" SUPPORTED
            if "!SUPPORTED!"=="1" (
                call :HandleOneFile "%%F"
            )
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
set "FILE_EXT=%~x1"

set /a TOTAL+=1

call :GetOutputPath "%SRC_FILE%" FILE_OUT REL_PATH
if not defined FILE_OUT exit /b 0

if exist "!FILE_OUT!\" (
    set /a SKIPPED_COUNT+=1
    echo [SKIP] !FILE_NAME!
    echo [SKIP] "%SRC_FILE%" ^-^> "!FILE_OUT!" >> "%LOG_FILE%"
    exit /b 0
)

echo [PARSE] "%SRC_FILE%" ^-^> "!FILE_OUT!" >> "%LOG_FILE%"

REM Копия с ASCII-именем: Docling кладёт файл во Temp с исходным именем — кириллица ломает Windows
call :MakeWorkCopy "%SRC_FILE%" WORK_SRC
if not defined WORK_SRC (
    set /a ERROR_COUNT+=1
    echo [ERROR] !FILE_NAME! ^(не удалось скопировать во временную папку^)
    echo [ERROR] copy failed "%SRC_FILE%" >> "%LOG_FILE%"
    exit /b 0
)

call :RunDoclingWithRetry "!WORK_SRC!" "!FILE_OUT!" "!FILE_EXT!"
set "PARSE_FAILED=0"
if errorlevel 1 set "PARSE_FAILED=1"

if exist "!WORK_SRC!" del /f /q "!WORK_SRC!" 2>nul

if "!PARSE_FAILED!"=="1" (
    set /a ERROR_COUNT+=1
    echo [ERROR] !FILE_NAME!
    echo [ERROR] "%SRC_FILE%" >> "%LOG_FILE%"
    if exist "!FILE_OUT!\" rd /s /q "!FILE_OUT!" 2>nul
) else (
    set /a PARSED_COUNT+=1
    echo [PARSE] !FILE_NAME!
    echo [PARSE] done "%SRC_FILE%" >> "%LOG_FILE%"
)
exit /b 0

REM ============================================================================
REM  Копия исходника в work\ с ASCII-именем (job_N.ext)
REM  Аргумент 2: имя переменной с полным путём копии
REM ============================================================================
:MakeWorkCopy
set "%~2="
set "SRC_COPY=%~1"
set "COPY_NAME=job_!TOTAL!_!RANDOM!!RANDOM!%~x1"
set "DEST_COPY=%WORK_DIR%\!COPY_NAME!"
copy /y "!SRC_COPY!" "!DEST_COPY!" >nul 2>&1
if errorlevel 1 (
    exit /b 1
)
set "%~2=!DEST_COPY!"
exit /b 0

REM ============================================================================
REM  Запуск Docling с повторами при WinError 32 (антивирус / блокировка Temp)
REM  Аргумент 1: путь к файлу для CLI (ASCII-имя)
REM  Аргумент 2: папка результата
REM  Аргумент 3: расширение с точкой (.pdf и т.д.)
REM ============================================================================
:RunDoclingWithRetry
set "CLI_SRC=%~1"
set "CLI_OUT=%~2"
set "CLI_EXT=%~3"
set /a ATTEMPT=0
set "USE_PYPDF=0"
if /i "!CLI_EXT!"==".pdf" set "USE_PYPDF=1"

:DoclingAttempt
set /a ATTEMPT+=1
echo Attempt !ATTEMPT!/!MAX_RETRIES! for "%CLI_SRC%" >> "%LOG_FILE%"

if "!USE_PYPDF!"=="1" (
    docling --to md --to json --to text --to html ^
        --output "!CLI_OUT!" ^
        --ocr ^
        --tables ^
        --table-mode accurate ^
        --image-export-mode referenced ^
        --pdf-backend pypdfium2 ^
        -v ^
        "!CLI_SRC!" >> "%LOG_FILE%" 2>&1
) else (
    docling --to md --to json --to text --to html ^
        --output "!CLI_OUT!" ^
        --ocr ^
        --tables ^
        --table-mode accurate ^
        --image-export-mode referenced ^
        -v ^
        "!CLI_SRC!" >> "%LOG_FILE%" 2>&1
)

if not errorlevel 1 exit /b 0

if !ATTEMPT! lss !MAX_RETRIES! (
    echo Retry after !RETRY_DELAY_SEC! sec... >> "%LOG_FILE%"
    timeout /t !RETRY_DELAY_SEC! /nobreak >nul
    goto DoclingAttempt
)
exit /b 1

REM ============================================================================
REM  Вычисление пути результата по исходному файлу
REM ============================================================================
:GetOutputPath
set "%~2="
set "%~3="
set "SRC_FULL=%~1"
set "SRC_DIR=%~dp1"
set "BASE_NAME=%~n1"

set "REL_PATH=!SRC_DIR:%INPUT_NORM%\=!"
if /i "!REL_PATH!"=="!SRC_DIR!" set "REL_PATH="

set "%~2=%OUTPUT_DIR%\!REL_PATH!!BASE_NAME!"
set "%~3=!REL_PATH!"
exit /b 0

REM ============================================================================
REM  Проверка расширения: поддерживается ли Docling
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
