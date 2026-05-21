@echo off
setlocal EnableExtensions EnableDelayedExpansion
goto :MainStart

REM ============================================================================
REM  Podprogrammy (metki pered :MainStart)
REM ============================================================================

:EnsureDir
if exist "%~1\." exit /b 0
mkdir "%~1" 2>nul
if exist "%~1\." exit /b 0
if not "%~1"=="%~dp1" call :EnsureDir "%~dp1"
mkdir "%~1" 2>nul
exit /b 0

:PrintLine
if "%~1"=="" (echo.) else (echo %~1)
exit /b 0

:PrintStatus
call :PrintLine "%~1 %~2"
exit /b 0

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

:AppendLog
>> "!LOG_FILE!" echo %~1 2>nul
if errorlevel 1 >> "%ROOT_DIR%\docling_fallback.log" echo %~1
exit /b 0

REM --------------------------------------------------------------------------
REM  Podderzhivaemye rasshireniya (sinhronizirovano s :ResolveFormatFlags)
REM  pdf docx xlsx pptx | md markdown adoc asciidoc tex html htm xhtml csv
REM  png jpg jpeg tif tiff bmp webp | wav mp3 m4a aac ogg flac | mp4 avi mov
REM  vtt | json | xml
REM --------------------------------------------------------------------------
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

REM  Nastrojka flagov Docling po rasshireniju (bez tochki): pdf, pptx, ...
:ResolveFormatFlags
set "FMT_FROM="
set "FMT_PIPELINE="
set "FMT_PDF="
set "FMT_TABLES=--no-tables"
set "FMT_OCR_ATT1=--no-ocr"
set "FMT_KIND=unknown"
set "IMG="
set "AUD="
set "VID="

if /i "%~1"=="pdf" (
    set "FMT_FROM=--from pdf"
    set "FMT_PDF=--pdf-backend pypdfium2"
    set "FMT_TABLES=--tables --table-mode accurate"
    set "FMT_OCR_ATT1=--ocr"
    set "FMT_KIND=pdf"
    exit /b 0
)
if /i "%~1"=="docx" (
    set "FMT_FROM=--from docx"
    set "FMT_TABLES=--tables --table-mode accurate"
    set "FMT_KIND=office"
    exit /b 0
)
if /i "%~1"=="xlsx" (
    set "FMT_FROM=--from xlsx"
    set "FMT_TABLES=--tables --table-mode accurate"
    set "FMT_KIND=office"
    exit /b 0
)
if /i "%~1"=="pptx" (
    set "FMT_FROM=--from pptx"
    set "FMT_TABLES=--tables --table-mode accurate"
    set "FMT_KIND=office"
    exit /b 0
)
if /i "%~1"=="md" (
    set "FMT_FROM=--from md"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="markdown" (
    set "FMT_FROM=--from md"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="adoc" (
    set "FMT_FROM=--from asciidoc"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="asciidoc" (
    set "FMT_FROM=--from asciidoc"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="tex" (
    set "FMT_FROM=--from latex"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="html" (
    set "FMT_FROM=--from html"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="htm" (
    set "FMT_FROM=--from html"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="xhtml" (
    set "FMT_FROM=--from html"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="csv" (
    set "FMT_FROM=--from csv"
    set "FMT_TABLES=--tables --table-mode accurate"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="vtt" (
    set "FMT_FROM=--from vtt"
    set "FMT_KIND=text"
    exit /b 0
)
if /i "%~1"=="json" (
    set "FMT_FROM=--from json_docling"
    set "FMT_KIND=json"
    exit /b 0
)
if /i "%~1"=="xml" (
    set "FMT_KIND=xml"
    exit /b 0
)
if /i "%~1"=="png" set "IMG=1"
if /i "%~1"=="jpg" set "IMG=1"
if /i "%~1"=="jpeg" set "IMG=1"
if /i "%~1"=="tif" set "IMG=1"
if /i "%~1"=="tiff" set "IMG=1"
if /i "%~1"=="bmp" set "IMG=1"
if /i "%~1"=="webp" set "IMG=1"
if defined IMG (
    set "FMT_FROM=--from image"
    set "FMT_OCR_ATT1=--ocr"
    set "FMT_KIND=image"
    exit /b 0
)
if /i "%~1"=="wav" set "AUD=1"
if /i "%~1"=="mp3" set "AUD=1"
if /i "%~1"=="m4a" set "AUD=1"
if /i "%~1"=="aac" set "AUD=1"
if /i "%~1"=="ogg" set "AUD=1"
if /i "%~1"=="flac" set "AUD=1"
if defined AUD (
    set "FMT_FROM=--from audio"
    set "FMT_PIPELINE=--pipeline asr --asr-model whisper_tiny"
    set "FMT_KIND=audio"
    exit /b 0
)
if /i "%~1"=="mp4" set "VID=1"
if /i "%~1"=="avi" set "VID=1"
if /i "%~1"=="mov" set "VID=1"
if defined VID (
    set "FMT_FROM=--from audio"
    set "FMT_PIPELINE=--pipeline asr --asr-model whisper_tiny"
    set "FMT_KIND=video"
    exit /b 0
)
exit /b 0

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

:IsOutputComplete
set "%~2=0"
if exist "%OUTPUT_DIR%\%~1.md" if exist "%OUTPUT_DIR%\%~1.html" set "%~2=1"
exit /b 0

:CleanupOutputArtifacts
set "KEY=%~1"
del /f /q "%OUTPUT_DIR%\!KEY!.md" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.html" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.json" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.txt" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.yaml" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.vtt" 2>nul
if exist "%OUTPUT_DIR%\!KEY!\." rd /s /q "%OUTPUT_DIR%\!KEY!" 2>nul
if exist "%OUTPUT_DIR%\!KEY!" del /f /q "%OUTPUT_DIR%\!KEY!" 2>nul
if exist "%OUTPUT_DIR%\!KEY!_artifacts\." rd /s /q "%OUTPUT_DIR%\!KEY!_artifacts" 2>nul
for /d %%D in ("%OUTPUT_DIR%\!KEY!*") do rd /s /q "%%~fD" 2>nul
exit /b 0

:RemoveUnwantedOutputs
set "KEY=%~1"
del /f /q "%OUTPUT_DIR%\!KEY!.json" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.txt" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.yaml" 2>nul
del /f /q "%OUTPUT_DIR%\!KEY!.vtt" 2>nul
if exist "%OUTPUT_DIR%\!KEY!\." rd /s /q "%OUTPUT_DIR%\!KEY!" 2>nul
if exist "%OUTPUT_DIR%\!KEY!_artifacts\." rd /s /q "%OUTPUT_DIR%\!KEY!_artifacts" 2>nul
for /d %%D in ("%OUTPUT_DIR%\!KEY!*") do rd /s /q "%%~fD" 2>nul
exit /b 0

:MakeWorkCopy
set "%~3="
set "DEST_COPY=%WORK_DIR%\%~2%~x1"
copy /y "%~1" "!DEST_COPY!" >nul 2>&1
if errorlevel 1 exit /b 1
set "%~3=!DEST_COPY!"
exit /b 0

:RunDoclingCommand
docling --to md --to html --output "%OUTPUT_DIR%" !FMT_FROM! !FMT_PIPELINE! !FMT_PDF! !OCR_FLAG! !FMT_TABLES! --image-export-mode placeholder -v "!CLI_SRC!" >> "!LOG_FILE!" 2>&1
exit /b 0

:RunDoclingWithRetry
set "CLI_SRC=%~1"
set "OUT_KEY=%~2"
set "CLI_EXT=%~3"
set "EXT_NORM=%CLI_EXT:~1%"
set /a ATTEMPT=0

call :ResolveFormatFlags "!EXT_NORM!"
if /i "!FMT_KIND!"=="unknown" (
    call :AppendLog "ERROR: neizvestnoe rasshirenie !EXT_NORM!"
    exit /b 1
)

:DoclingAttempt
set /a ATTEMPT+=1
call :CleanupOutputArtifacts "!OUT_KEY!"
call :AppendLog "Attempt !ATTEMPT!/!MAX_ATTEMPTS! kind=!FMT_KIND! ext=.!EXT_NORM! key=!OUT_KEY!"

set "OCR_FLAG=!FMT_OCR_ATT1!"
if !ATTEMPT! geq 2 (
    if /i "!FMT_KIND!"=="pdf" set "OCR_FLAG=--no-ocr"
    if /i "!FMT_KIND!"=="image" set "OCR_FLAG=--no-ocr"
)

call :RunDoclingCommand

if not errorlevel 1 (
    call :IsOutputComplete "!OUT_KEY!" OUT_DONE
    if "!OUT_DONE!"=="1" (
        call :RemoveUnwantedOutputs "!OUT_KEY!"
        exit /b 0
    )
    call :AppendLog "WARN: net .md/.html dlya !OUT_KEY!"
)

if !ATTEMPT! lss !MAX_ATTEMPTS! (
    call :AppendLog "Retry !RETRY_DELAY_SEC!s..."
    timeout /t !RETRY_DELAY_SEC! /nobreak >nul
    goto :DoclingAttempt
)

call :CleanupOutputArtifacts "!OUT_KEY!"
exit /b 1

:HandleOneFile
set "SRC_FILE=%~1"
set "FILE_EXT=%~2"
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

call :AppendLog "[PARSE] %SRC_FILE% key=!OUT_KEY! ext=!FILE_EXT!"

call :MakeWorkCopy "%SRC_FILE%" "!OUT_KEY!" WORK_SRC
if not defined WORK_SRC (
    set /a ERROR_COUNT+=1
    call :PrintStatus "[ERROR]" "%~nx1"
    call :AppendLog "[ERROR] copy failed - fajl otkrojte/zakroyte v Office/pleere"
    exit /b 0
)

call :RunDoclingWithRetry "!WORK_SRC!" "!OUT_KEY!" ".!FILE_EXT!"
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
    call :AppendLog "[PARSE] done"
    call :RemoveUnwantedOutputs "!OUT_KEY!"
)
exit /b 0

:ProcessFile
set "PF_NAME=%~nx1"
if "!PF_NAME:~0,2!"=="~$" exit /b 0
if /i "%~x1"=="" exit /b 0
set "PF_EXT=%~x1"
set "PF_EXT=!PF_EXT:~1!"
call :IsSupportedExt "!PF_EXT!" SUPPORTED
if not "!SUPPORTED!"=="1" exit /b 0
call :HandleOneFile "%~1" "!PF_EXT!"
exit /b 0

REM ============================================================================
:MainStart

set "SCRIPT_VERSION=1.3"
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
set /a MAX_ATTEMPTS=3
set /a RETRY_DELAY_SEC=5

call :PrintLine "========================================"
call :PrintLine "Docling batch v!SCRIPT_VERSION!"
call :PrintLine "Vyhod: md + html | vse formaty Docling"
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

where docling >nul 2>&1
if errorlevel 1 (
    call :PrintLine "Docling ne najden: pip install docling"
    goto :EndScript
)

if not exist "%INPUT_DIR%" (
    call :PrintLine "[ERROR] Net papki docs:"
    call :PrintLine "%INPUT_DIR%"
    goto :EndScript
)

call :AppendLog "Started v!SCRIPT_VERSION!"
call :PrintLine "Input:  %INPUT_DIR%"
call :PrintLine "Output: %OUTPUT_DIR%"
call :PrintLine "Log:    !LOG_FILE!"

for /r "%INPUT_DIR%" %%F in (*) do call :ProcessFile "%%~fF"

call :PrintLine "========================================"
call :PrintLine "Total: !TOTAL! | Parsed: !PARSED_COUNT! | Skip: !SKIPPED_COUNT! | Err: !ERROR_COUNT!"
call :PrintLine "========================================"
call :PrintLine "Log: !LOG_FILE!"

goto :EndScript

:EndScript
echo.
echo Press any key to close...
pause >nul
endlocal
exit /b 0
