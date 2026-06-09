@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "run_docling_parse.exe" (
    echo NET run_docling_parse.exe — zapusk build.bat
    call "%~dp0build.bat"
    if errorlevel 1 (
        echo Sborka ne udalas.
        pause
        exit /b 1
    )
)

title Docling batch v2.0
cmd /k "%~dp0run_docling_parse.exe"
exit /b 0
