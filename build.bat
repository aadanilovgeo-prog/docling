@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "OUT=run_docling_parse_v3.0.exe"
set "SRC=src\run_docling_parse.c"

echo Building %OUT% ...

where cl >nul 2>&1
if not errorlevel 1 (
    cl /nologo /W4 /O2 /utf-8 /Fe:%OUT% %SRC% user32.lib
    if errorlevel 1 exit /b 1
    echo OK: MSVC build -^> %OUT%
    exit /b 0
)

where gcc >nul 2>&1
if not errorlevel 1 (
    gcc -Wall -Wextra -O2 -municode -mconsole -o %OUT% %SRC% -lkernel32
    if errorlevel 1 exit /b 1
    echo OK: MinGW build -^> %OUT%
    exit /b 0
)

echo OSHIBKA: nuzhen MSVC (cl) ili MinGW (gcc) v PATH
exit /b 1
