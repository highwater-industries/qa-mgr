@echo off
REM Quick start script for QA Manager
cd /d "%~dp0"

REM Check if venv exists, if not run setup
if not exist ".venv" (
    echo Virtual environment not found. Running setup...
    uv venv --python 3.12.10
    uv pip install -e .
    if errorlevel 1 exit /b 1
)

REM Activate venv and start server
call .venv\Scripts\activate.bat
python scripts\server.py start
