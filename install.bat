@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
for %%V in (3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 if not defined PYTHON_CMD set "PYTHON_CMD=py -%%V"
)

if not defined PYTHON_CMD (
    echo [Daniya] Python 3.10-3.12 was not found.
    echo Please install Python 3.10, 3.11, or 3.12 and enable "Add Python to PATH".
    echo Download: https://www.python.org/downloads/
    exit /b 1
)

echo [Daniya] Creating virtual environment with %PYTHON_CMD%...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo [Daniya] Failed to create virtual environment.
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [Daniya] Dependency installation failed. Check network and Python version.
    exit /b 1
)

echo [Daniya] Install complete. You can run run.bat now.
