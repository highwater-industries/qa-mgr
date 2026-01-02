@echo off
REM Quick stop script for QA Manager
cd /d "%~dp0"

REM Try with venv first
if exist ".venv" (
    call .venv\Scripts\activate.bat
    python scripts\server.py stop
) else (
    echo Virtual environment not found. Server may not be running.
    py -3.12 scripts\server.py stop
)
