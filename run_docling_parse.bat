@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  Docling CLI - batch parse (incremental)
REM  https://docling-project.github.io/docling/
REM ============================================================================

cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>&1

call :PrintLine "========================================"
call :PrintLine "Docling batch: START"
call :PrintLine "BAT file: %~f0"
call :PrintLine "========================================"

REM --- Paths ------------------------------------------------------------------
set "INPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\docs"
set "OUTPUT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\parsed"
set "LOG_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\logs"
set "WORK_DIR=C:\Users\andrey.danilov\Documents\VTB\docling\work"
set "TMP_DIR=%WORK_DIR%\tmp"

set "INPUT_NORM=%INPUT_DIR%"
if /i "%INPUT_NORM:~-1%"=="\" set "INPUT_NORM=%INPUT_NORM:~0,-1%"

REM --- Counters ---------------------------------------------------------------
set /a TOTAL=0
set /a PARSED_COUNT=0
set /a SKIPPED_COUNT=0
set /a ERROR_COUNT=0
set /a MAX_RETRIES=3
set /a RETRY_DELAY_SEC=5

REM --- Log file name (no wmic - works on Win11) -------------------------------
call :MakeLogTimestamp LOG_STAMP
if not defined LOG_STAMP (
    call :PrintLine "[ERROR] Cannot build log timestamp."
    goto :FinishWithPause
)
set "LOG_FILE=%LOG_DIR%\docling_%LOG_STAMP%.log"

where docling >nul 2>&1
if errorlevel 1 (
    call :PrintLine "Docling not found. Install docling and add it to PATH."
    call :PrintLine "Example: pip install docling"
    goto :FinishWithPause
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%" 2>nul
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%" 2>nul
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" 2>nul

set "TEMP=%TMP_DIR%"
set "TMP=%TMP_DIR%"

if not exist "%INPUT_DIR%" (
    call :PrintLine "[ERROR] Input folder not found:"
    call :PrintLine "%INPUT_DIR%"
    goto :FinishWithPause
)

(
    echo ============================================================
    echo Docling batch parse
    echo Started: %LOG_STAMP%
    echo Input:   "%INPUT_DIR%"
    echo Output:  "%OUTPUT_DIR%"
    echo Work:    "%WORK_DIR%"
    echo Temp:    "%TMP_DIR%"
    echo Log:     "%LOG_FILE%"
    echo ============================================================
) >> "%LOG_FILE%" 2>&1

call :PrintLine ""
call :PrintLine "Input:  %INPUT_DIR%"
call :PrintLine "Output: %OUTPUT_DIR%"
call :PrintLine "Log:    %LOG_FILE%"
call :PrintLine "Scanning files..."
call :PrintLine ""

for /r "%INPUT_DIR%" %%F in (*) do (
    set "ITEM_NAME=%%~nxF"
    if not "!ITEM_NAME:~0,2!"=="~$" (
        if /i not "%%~xF"=="" (
            set "ITEM_EXT=%%~xF"
            set "ITEM_EXT=!ITEM_EXT:~1!"
            call :IsSupportedExt "!ITEM_EXT!" SUPPORTED
            if "!SUPPORTED!"=="1" (
                call :HandleOneFile "%%~fF"
            )
        )
    )
)

call :PrintLine ""
call :PrintLine "========================================"
call :PrintLine "Total files found: !TOTAL!"
call :PrintLine "Parsed:            !PARSED_COUNT!"
call :PrintLine "Skipped:           !SKIPPED_COUNT!"
call :PrintLine "Errors:            !ERROR_COUNT!"
call :PrintLine "========================================"

if !TOTAL! equ 0 (
    call :PrintLine "WARNING: No supported files found in docs folder."
    call :PrintLine "Put PDF/DOCX/... into: %INPUT_DIR%"
)

call :PrintLine "Log file: %LOG_FILE%"

(
    echo.
    echo Finished
    echo Total: !TOTAL!
    echo Parsed: !PARSED_COUNT!
    echo Skipped: !SKIPPED_COUNT!
    echo Errors: !ERROR_COUNT!
) >> "%LOG_FILE%" 2>&1

goto :FinishWithPause

REM ============================================================================
:HandleOneFile
set "SRC_FILE=%~1"
set /a TOTAL+=1

call :GetOutputPath "%SRC_FILE%" FILE_OUT
if not defined FILE_OUT exit /b 0

call :DirExists "!FILE_OUT!" DIR_EXISTS
if "!DIR_EXISTS!"=="1" (
    set /a SKIPPED_COUNT+=1
    call :PrintStatus "[SKIP]" "%~nx1"
    echo [SKIP] "%SRC_FILE%" >> "%LOG_FILE%"
    exit /b 0
)

echo [PARSE] "%SRC_FILE%" -^> "!FILE_OUT!" >> "%LOG_FILE%"

call :MakeWorkCopy "%SRC_FILE%" WORK_SRC
if not defined WORK_SRC (
    set /a ERROR_COUNT+=1
    call :PrintStatus "[ERROR]" "%~nx1"
    echo [ERROR] copy failed "%SRC_FILE%" >> "%LOG_FILE%"
    exit /b 0
)

call :RunDoclingWithRetry "!WORK_SRC!" "!FILE_OUT!" "%~x1"
set "PARSE_FAILED=0"
if errorlevel 1 set "PARSE_FAILED=1"

if exist "!WORK_SRC!" del /f /q "!WORK_SRC!" 2>nul

if "!PARSE_FAILED!"=="1" (
    set /a ERROR_COUNT+=1
    call :PrintStatus "[ERROR]" "%~nx1"
    echo [ERROR] "%SRC_FILE%" >> "%LOG_FILE%"
    call :RemoveDir "!FILE_OUT!"
) else (
    set /a PARSED_COUNT+=1
    call :PrintStatus "[PARSE]" "%~nx1"
    echo [PARSE] done "%SRC_FILE%" >> "%LOG_FILE%"
)
exit /b 0

REM ============================================================================
:MakeWorkCopy
set "%~2="
set "DEST_COPY=%WORK_DIR%\job_!TOTAL!_!RANDOM!!RANDOM!%~x1"
copy /y "%~1" "!DEST_COPY!" >nul 2>&1
if errorlevel 1 exit /b 1
set "%~2=!DEST_COPY!"
exit /b 0

REM ============================================================================
:RunDoclingWithRetry
set "CLI_SRC=%~1"
set "CLI_OUT=%~2"
set "CLI_EXT=%~3"
set /a ATTEMPT=0
set "USE_PYPDF=0"
if /i "%CLI_EXT%"==".pdf" set "USE_PYPDF=1"

:DoclingAttempt
set /a ATTEMPT+=1
echo Attempt !ATTEMPT!/!MAX_RETRIES!: "%CLI_SRC%" >> "%LOG_FILE%"

if "!USE_PYPDF!"=="1" (
    docling --to md --to json --to text --to html --output "%CLI_OUT%" --ocr --tables --table-mode accurate --image-export-mode referenced --pdf-backend pypdfium2 -v "%CLI_SRC%" >> "%LOG_FILE%" 2>&1
) else (
    docling --to md --to json --to text --to html --output "%CLI_OUT%" --ocr --tables --table-mode accurate --image-export-mode referenced -v "%CLI_SRC%" >> "%LOG_FILE%" 2>&1
)

if not errorlevel 1 exit /b 0
if !ATTEMPT! lss !MAX_RETRIES! (
    echo Retry in !RETRY_DELAY_SEC! sec... >> "%LOG_FILE%"
    timeout /t !RETRY_DELAY_SEC! /nobreak >nul
    goto DoclingAttempt
)
exit /b 1

REM ============================================================================
:GetOutputPath
set "%~2="
set "SRC_DIR=%~dp1"
set "BASE_NAME=%~n1"
set "REL_PATH=%SRC_DIR%"
set "REL_PATH=!REL_PATH:%INPUT_NORM%\=!"
if /i "!REL_PATH!"=="%~dp1" set "REL_PATH="
set "%~2=%OUTPUT_DIR%\!REL_PATH!!BASE_NAME!"
exit /b 0

REM ============================================================================
:DirExists
set "%~2=0"
if exist "%~1\." set "%~2=1"
exit /b 0

REM ============================================================================
:RemoveDir
if exist "%~1\." rd /s /q "%~1" 2>nul
exit /b 0

REM ============================================================================
:PrintStatus
call :PrintLine "%~1 %~2"
exit /b 0

REM ============================================================================
:PrintLine
echo %~1
exit /b 0

REM ============================================================================
:MakeLogTimestamp
set "%~1="
set "TS=%date%_%time%"
set "TS=!TS: =0!"
set "TS=!TS:/=-!"
set "TS=!TS::=-!"
set "TS=!TS:,=!"
set "%~1=!TS!"
exit /b 0

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

REM ============================================================================
:FinishWithPause
echo.
echo Press any key to close...
pause >nul
endlocal
exit /b 0
