@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Daniya] Virtual environment not found. Please run install.bat first.
    exit /b 1
)

if not exist "assets\placeholder\app.ico" (
    echo [Daniya] Missing assets\placeholder\app.ico. Cannot package.
    exit /b 1
)

call .venv\Scripts\activate.bat

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name DaniyaSummerPet ^
  --icon assets\placeholder\app.ico ^
  --add-data "assets\placeholder;assets\placeholder" ^
  --add-data "config;config" ^
  --add-data "docs;docs" ^
  --add-data "README.md;." ^
  main.py

if errorlevel 1 (
    echo [Daniya] Packaging failed. Check the PyInstaller output above.
    exit /b 1
)

echo [Daniya] Package complete: dist\DaniyaSummerPet.exe
echo [Daniya] To use private assets, create assets\private\daniya_summer\ next to the exe and add normal1.png, normal2.png, app.ico.
