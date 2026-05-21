@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  Docling CLI - inkrementalnyj parsing
REM  Versiya: 1.0
REM  Vyhod: tolko fajly v parsed\ (bez podpapok)
REM  Pri oshibke: 3 popytki (1 + 2 povtora), mezhdu nimi ochistka musora
REM ============================================================================

set "SCRIPT_VERSION=1.0"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>&1

set "ROOT_DIR=C:\Users\andrey.danilov\Documents\VTB\docling"
set "INPUT_DIR=%ROOT_DIR%\docs"
set "OUTPUT_DIR=%ROOT_DIR%\parsed"
set "LOG_DIR=%ROOT_DIR%\logs"
set "WORK_DIR=%ROOT_DIR%\work"
set "TMP_DIR=%WORK_DIR%\tmp"

set "INPUT_NORM=%INPUT_DIR%"
if /i "%INPUT_NORM:~-1%"=="\" set "INPUT_NORM=%INPUT_NORM:~0,-1%"

set /a TOTAL=0
set /a PARSED_COUNT=0
set /a SKIPPED_COUNT=0
set /a ERROR_COUNT=0
REM 3 popytki = 1 zapusk + 2 povtora pri oshibke
set /a MAX_ATTEMPTS=3
set /a RETRY_DELAY_SEC=5

call :PrintLine "========================================"
call :PrintLine "Docling batch: START v!SCRIPT_VERSION!"
call :PrintLine "BAT: %~f0"
call :PrintLine "Root: %ROOT_DIR%"
call :PrintLine "========================================"

call :EnsureDir "%OUTPUT_DIR%"
call :EnsureDir "%LOG_DIR%"
call :EnsureDir "%WORK_DIR%"
call :EnsureDir "%TMP_DIR%"

set "TEMP=%TMP_DIR%"
set "TMP=%TMP_DIR%"

call :MakeLogTimestamp LOG_STAMP
if not defined LOG_STAMP set "LOG_STAMP=run_%RANDOM%"
set "LOG_FILE=%LOG_DIR%\docling_%LOG_STAMP%.log"
type nul > "%LOG_FILE%" 2>nul
if not exist "%LOG_FILE%" (
    set "LOG_FILE=%ROOT_DIR%\docling_%LOG_STAMP%.log"
    type nul > "%LOG_FILE%" 2>nul
)

where docling >nul 2>&1
if errorlevel 1 (
    call :PrintLine "Docling ne najden. Ustanovite: pip install docling"
    call :AppendLog "ERROR: docling not in PATH"
    goto :FinishWithPause
)

if not exist "%INPUT_DIR%" (
    call :PrintLine "[ERROR] Papka docs ne najdena:"
    call :PrintLine "%INPUT_DIR%"
    call :AppendLog "ERROR: input dir missing"
    goto :FinishWithPause
)

call :AppendLog "============================================================"
call :AppendLog "Started v!SCRIPT_VERSION!"
call :AppendLog "Input: %INPUT_DIR%"
call :AppendLog "Output: %OUTPUT_DIR% (flat, no subfolders)"

call :PrintLine ""
call :PrintLine "Input:  %INPUT_DIR%"
call :PrintLine "Output: %OUTPUT_DIR%"
call :PrintLine "Log:    !LOG_FILE!"
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
    call :PrintLine "WARNING: Net podderzhivaemyh fajlov v docs"
)

call :PrintLine ""
call :PrintLine "Log file:"
call :PrintLine "!LOG_FILE!"
call :AppendLog "Finished. Total=!TOTAL! Parsed=!PARSED_COUNT! Skipped=!SKIPPED_COUNT! Errors=!ERROR_COUNT!"

goto :FinishWithPause

REM ============================================================================
:HandleOneFile
set "SRC_FILE=%~1"
set /a TOTAL+=1

call :GetOutputKey "%SRC_FILE%" OUT_KEY
if not defined OUT_KEY exit /b 0

call :IsOutputComplete "!OUT_KEY!" OUT_DONE
if "!OUT_DONE!"=="1" (
    set /a SKIPPED_COUNT+=1
    call :PrintStatus "[SKIP]" "%~nx1"
    call :AppendLog "[SKIP] %SRC_FILE%"
    exit /b 0
)

call :AppendLog "[PARSE] %SRC_FILE% key=!OUT_KEY!"

call :MakeWorkCopy "%SRC_FILE%" "!OUT_KEY!" WORK_SRC
if not defined WORK_SRC (
    set /a ERROR_COUNT+=1
    call :PrintStatus "[ERROR]" "%~nx1"
    call :AppendLog "[ERROR] copy failed: %SRC_FILE%"
    exit /b 0
)

call :RunDoclingWithRetry "!WORK_SRC!" "!OUT_KEY!" "%~x1"
set "PARSE_FAILED=0"
if errorlevel 1 set "PARSE_FAILED=1"

if exist "!WORK_SRC!" del /f /q "!WORK_SRC!" 2>nul

if "!PARSE_FAILED!"=="1" (
    set /a ERROR_COUNT+=1
    call :PrintStatus "[ERROR]" "%~nx1"
    call :AppendLog "[ERROR] %SRC_FILE%"
    call :CleanupOutputArtifacts "!OUT_KEY!"
) else (
    set /a PARSED_COUNT+=1
    call :PrintStatus "[PARSE]" "%~nx1"
    call :AppendLog "[PARSE] done: %SRC_FILE%"
)
exit /b 0

REM ============================================================================
:MakeWorkCopy
set "%~3="
set "DEST_COPY=%WORK_DIR%\%~2%~x1"
copy /y "%~1" "!DEST_COPY!" >nul 2>&1
if errorlevel 1 exit /b 1
set "%~3=!DEST_COPY!"
exit /b 0

REM ============================================================================
:RunDoclingWithRetry
set "CLI_SRC=%~1"
set "OUT_KEY=%~2"
set "CLI_EXT=%~3"
set /a ATTEMPT=0
set "USE_PYPDF=0"
if /i "%CLI_EXT%"==".pdf" set "USE_PYPDF=1"

:DoclingAttempt
set /a ATTEMPT+=1
call :CleanupOutputArtifacts "!OUT_KEY!"
call :AppendLog "Attempt !ATTEMPT!/!MAX_ATTEMPTS! key=!OUT_KEY! src=!CLI_SRC!"

REM Popytka 1: OCR; popytki 2-3: bez OCR (obhod oshibki zagruzki RapidOCR)
set "OCR_FLAG=--ocr"
if !ATTEMPT! geq 2 set "OCR_FLAG=--no-ocr"

if "!USE_PYPDF!"=="1" (
    docling --to md --to json --to text --to html --output "%OUTPUT_DIR%" !OCR_FLAG! --tables --table-mode accurate --image-export-mode referenced --pdf-backend pypdfium2 -v "!CLI_SRC!" >> "!LOG_FILE!" 2>&1
) else (
    docling --to md --to json --to text --to html --output "%OUTPUT_DIR%" !OCR_FLAG! --tables --table-mode accurate --image-export-mode referenced -v "!CLI_SRC!" >> "!LOG_FILE!" 2>&1
)

if not errorlevel 1 (
    call :IsOutputComplete "!OUT_KEY!" OUT_DONE
    if "!OUT_DONE!"=="1" exit /b 0
    call :AppendLog "WARN: docling exit 0 but output files missing for !OUT_KEY!"
)

if !ATTEMPT! lss !MAX_ATTEMPTS! (
    call :AppendLog "Retry in !RETRY_DELAY_SEC! sec..."
    timeout /t !RETRY_DELAY_SEC! /nobreak >nul
    goto DoclingAttempt
)

call :CleanupOutputArtifacts "!OUT_KEY!"
exit /b 1

REM ============================================================================
REM  Klyuch vyhoda: imya bez rasshireniya + prefiks podpapki (cherez _)
REM  docs\a\report.pdf -> a_report
REM  docs\report.pdf   -> report
REM ============================================================================
:GetOutputKey
set "%~2="
set "SRC_DIR=%~dp1"
set "BASE_NAME=%~n1"
set "REL_PATH=%SRC_DIR%"
set "REL_PATH=!REL_PATH:%INPUT_NORM%\=!"
if /i "!REL_PATH!"=="%~dp1" set "REL_PATH="
if defined REL_PATH (
    set "REL_PATH=!REL_PATH:\=_!"
    if "!REL_PATH:~-1!"=="_" set "REL_PATH=!REL_PATH:~0,-1!"
    set "%~2=!REL_PATH!_!BASE_NAME!"
) else (
    set "%~2=!BASE_NAME!"
)
exit /b 0

REM ============================================================================
REM  Proverka: fajly rezultata uzhe v parsed\ (bez podpapok)
REM ============================================================================
:IsOutputComplete
set "%~2=0"
if exist "%OUTPUT_DIR%\%~1.md" if exist "%OUTPUT_DIR%\%~1.json" set "%~2=1"
exit /b 0

REM ============================================================================
REM  Udalenie chastichnyh rezultatov i staryh papok s tem zhe imenem
REM ============================================================================
:CleanupOutputArtifacts
set "KEY=%~1"
del /f /q "%OUTPUT_DIR%\!KEY!.md" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.json" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.html" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.txt" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.yaml" 2>nul
if exist "%OUTPUT_DIR%\!KEY!\." (
    rd /s /q "%OUTPUT_DIR%\!KEY!" 2>nul
) else (
    if exist "%OUTPUT_DIR%\!KEY!" del /f /q "%OUTPUT_DIR%\!KEY!" 2>nul
)
exit /b 0

REM ============================================================================
:EnsureDir
if exist "%~1\." exit /b 0
mkdir "%~1" 2>nul
if exist "%~1\." exit /b 0
if not "%~1"=="%~dp1" call :EnsureDir "%~dp1"
mkdir "%~1" 2>nul
exit /b 0

REM ============================================================================
:AppendLog
>> "!LOG_FILE!" echo %~1 2>nul
if errorlevel 1 >> "%ROOT_DIR%\docling_fallback.log" echo %~1
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
set "TS=%RANDOM%_%RANDOM%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TS=!TS: =0!"
set "TS=!TS:,=!"
set "TS=!TS:/=-!"
set "TS=!TS::=-!"
set "TS=!TS:.=-!"
set "TS=!TS:(=-!"
set "TS=!TS:)=-!"
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
