@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "APP_NAME=DaniyaSummerPet"
set "VERSION=v0.44"
set "PACKAGE_NAME=DaniyaSummerPet-v0.44-win-x64"
set "PYTHON_EXE=python"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if not exist "main.py" (
    echo [Daniya] Missing main.py. Cannot package.
    pause
    exit /b 1
)

if not exist "assets\placeholder\app.ico" (
    echo [Daniya] Missing assets\placeholder\app.ico. Packaging will continue with the default icon.
    set "ICON_ARGS="
) else (
    set "ICON_ARGS=--icon assets\placeholder\app.ico"
)

echo [Daniya] Using Python:
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo [Daniya] Python is not available.
    pause
    exit /b 1
)

echo [Daniya] Checking PyInstaller...
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [Daniya] Installing PyInstaller into the active environment...
    "%PYTHON_EXE%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [Daniya] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo [Daniya] Cleaning old build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "release\%PACKAGE_NAME%" rmdir /s /q "release\%PACKAGE_NAME%"
if exist "release\test_run_v0.44" rmdir /s /q "release\test_run_v0.44"
if exist "release\%PACKAGE_NAME%.zip" del /q "release\%PACKAGE_NAME%.zip"
if not exist "release" mkdir "release"

echo [Daniya] Running PyInstaller...
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "%APP_NAME%" ^
  %ICON_ARGS% ^
  --add-data "assets\placeholder;assets\placeholder" ^
  --add-data "config;config" ^
  --add-data "characters;characters" ^
  --add-data "docs;docs" ^
  --add-data "README.md;." ^
  --add-data "LICENSE;." ^
  --add-data ".env.example;." ^
  main.py

if errorlevel 1 (
    echo [Daniya] Packaging failed. Check the PyInstaller output above.
    pause
    exit /b 1
)

if not exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    echo [Daniya] Expected exe was not found: dist\%APP_NAME%\%APP_NAME%.exe
    pause
    exit /b 1
)

echo [Daniya] Creating release directory...
mkdir "release\%PACKAGE_NAME%"
robocopy "dist\%APP_NAME%" "release\%PACKAGE_NAME%" /E /XD "assets\private" "data" "models" "backups" "__pycache__" /XF ".env" "*.log" "*.spec" >nul
if %ERRORLEVEL% GEQ 8 (
    echo [Daniya] Failed to copy PyInstaller output.
    pause
    exit /b 1
)

echo [Daniya] Copying public project files...
if not exist "release\%PACKAGE_NAME%\assets\placeholder" robocopy "assets\placeholder" "release\%PACKAGE_NAME%\assets\placeholder" /E >nul
if not exist "release\%PACKAGE_NAME%\characters" robocopy "characters" "release\%PACKAGE_NAME%\characters" /E >nul
if not exist "release\%PACKAGE_NAME%\config" robocopy "config" "release\%PACKAGE_NAME%\config" /E >nul
if not exist "release\%PACKAGE_NAME%\docs" robocopy "docs" "release\%PACKAGE_NAME%\docs" /E >nul
copy /Y "README.md" "release\%PACKAGE_NAME%\README.md" >nul
copy /Y "LICENSE" "release\%PACKAGE_NAME%\LICENSE" >nul
copy /Y ".env.example" "release\%PACKAGE_NAME%\.env.example" >nul
if exist "config\app_config.example.json" copy /Y "config\app_config.example.json" "release\%PACKAGE_NAME%\config\app_config.json" >nul
if exist "config\api_config.example.json" copy /Y "config\api_config.example.json" "release\%PACKAGE_NAME%\config\api_config.json" >nul

echo [Daniya] Removing forbidden package content if present...
if exist "release\%PACKAGE_NAME%\.env" del /q "release\%PACKAGE_NAME%\.env"
if exist "release\%PACKAGE_NAME%\assets\private" rmdir /s /q "release\%PACKAGE_NAME%\assets\private"
if exist "release\%PACKAGE_NAME%\data" rmdir /s /q "release\%PACKAGE_NAME%\data"
if exist "release\%PACKAGE_NAME%\models" rmdir /s /q "release\%PACKAGE_NAME%\models"
if exist "release\%PACKAGE_NAME%\backups" rmdir /s /q "release\%PACKAGE_NAME%\backups"
for /r "release\%PACKAGE_NAME%" %%F in (*.log *.spec) do del /q "%%F"
for /d /r "release\%PACKAGE_NAME%" %%D in (__pycache__) do rmdir /s /q "%%D" 2>nul

echo [Daniya] Creating zip package...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\%PACKAGE_NAME%\*' -DestinationPath 'release\%PACKAGE_NAME%.zip' -Force"
if errorlevel 1 (
    echo [Daniya] Zip creation failed.
    pause
    exit /b 1
)

echo [Daniya] Package complete:
echo [Daniya] release\%PACKAGE_NAME%\%APP_NAME%.exe
echo [Daniya] release\%PACKAGE_NAME%.zip
echo [Daniya] Private assets, .env, data, models, backups, build, and dist work directories are not included in the zip.
