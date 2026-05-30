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

echo [Daniya] Creating desktop shortcut...
powershell -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; ^
    $shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\达妮娅桌宠.lnk'); ^
    $shortcut.TargetPath = '%~dp0run.bat'; ^
    $shortcut.WorkingDirectory = '%~dp0'; ^
    $shortcut.IconLocation = '%~dp0assets\placeholder\icon.ico,0'; ^
    $shortcut.Save()"

echo.
echo [Daniya] ====================================
echo [Daniya] Install complete!
echo [Daniya] Desktop shortcut created: 达妮娅桌宠
echo [Daniya] Double-click it anytime to start.
echo [Daniya] ====================================

echo.
echo Starting Daniya for the first time...
call run.bat
