@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "APP_NAME=DaniyaSummerPet"
set "VERSION=unknown"
set "PACKAGE_NAME=unknown"
if not defined PYTHON_EXE set "PYTHON_EXE=python"
set "PKG_STAGING=%TEMP%\%APP_NAME%_package_%RANDOM%_%RANDOM%"
set "SAFE_CONFIG=%PKG_STAGING%\config"
set "SAFE_DOCS=%PKG_STAGING%\docs"

if defined DANIYA_PACK_PYTHON (
    set "PYTHON_EXE=%DANIYA_PACK_PYTHON%"
) else if exist ".venv\Scripts\python.exe" (
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

echo [Daniya] Loading version from src/version.py...
for /f "tokens=2 delims==" %%v in ('findstr "APP_VERSION" src\version.py') do (
    set "VERSION=%%v"
    set "VERSION=!VERSION: =!"
    set "VERSION=!VERSION:"=!"
    set "VERSION=!VERSION:'=!"
)
set "PACKAGE_NAME=%APP_NAME%-!VERSION!-win-x64"
echo [Daniya] Dynamic package name: !PACKAGE_NAME!

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
if exist "release\!PACKAGE_NAME!" rmdir /s /q "release\!PACKAGE_NAME!"
if exist "release\test_run_v0.49" rmdir /s /q "release\test_run_v0.49"
if exist "release\!PACKAGE_NAME!.zip" del /q "release\!PACKAGE_NAME!.zip"
if not exist "release" mkdir "release"
if exist "%PKG_STAGING%" rmdir /s /q "%PKG_STAGING%"

echo [Daniya] Preparing public package input...
mkdir "%SAFE_CONFIG%"
mkdir "%SAFE_DOCS%"

if not exist "config\app_config.example.json" (
    echo [Daniya] Missing config\app_config.example.json. Cannot package safely.
    pause
    exit /b 1
)
copy /Y "config\app_config.example.json" "%SAFE_CONFIG%\app_config.json" >nul
copy /Y "config\app_config.example.json" "%SAFE_CONFIG%\app_config.example.json" >nul

if not exist "config\api_config.example.json" (
    echo [Daniya] Missing config\api_config.example.json. Cannot package safely.
    pause
    exit /b 1
)
copy /Y "config\api_config.example.json" "%SAFE_CONFIG%\api_config.example.json" >nul

if not exist "config\model_profiles.json" (
    echo [Daniya] Missing config\model_profiles.json. Cannot package safely.
    pause
    exit /b 1
)
copy /Y "config\model_profiles.json" "%SAFE_CONFIG%\model_profiles.json" >nul

for %%F in (bookmarks.json model_catalog.json profile.json provider_capabilities.json setup_config.json system_prompt.txt) do (
    if exist "config\%%F" copy /Y "config\%%F" "%SAFE_CONFIG%\%%F" >nul
)

for %%F in (
    index.md
    installation.md
    first_run_guide.md
    api_config.md
    troubleshooting.md
    help.md
    character_pack_guide.md
    asset_policy.md
    release_checklist.md
    dev_workflow.md
    behavior_engine.md
    SETTINGS_CENTER.md
    SECURITY_AUDIT.md
    local_models.md
    LLM_PROVIDERS.md
    CUSTOM_API_PROVIDER_GUIDE.md
) do (
    if exist "docs\%%F" copy /Y "docs\%%F" "%SAFE_DOCS%\%%F" >nul
)

echo [Daniya] Running PyInstaller...
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "%APP_NAME%" ^
  %ICON_ARGS% ^
  --add-data "assets\placeholder;assets\placeholder" ^
  --add-data "assets\icons;assets\icons" ^
  --add-data "%SAFE_CONFIG%;config" ^
  --add-data "characters\daniya\actions.yaml;characters\daniya" ^
  --add-data "characters\daniya\character.yaml;characters\daniya" ^
  --add-data "characters\daniya\events.yaml;characters\daniya" ^
  --add-data "characters\daniya\lore.md;characters\daniya" ^
  --add-data "characters\daniya\lore_index.yaml;characters\daniya" ^
  --add-data "characters\daniya\prompt_pack.md;characters\daniya" ^
  --add-data "characters\daniya\relationship.yaml;characters\daniya" ^
  --add-data "characters\daniya\speech.yaml;characters\daniya" ^
  --add-data "characters\daniya\story.yaml;characters\daniya" ^
  --add-data "characters\template;characters\template" ^
  --add-data "%SAFE_DOCS%;docs" ^
  --add-data "README.md;." ^
  --add-data "LICENSE;." ^
  --add-data "CHANGELOG.md;." ^
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
mkdir "release\!PACKAGE_NAME!"
robocopy "dist\%APP_NAME%" "release\!PACKAGE_NAME!" /E /XD "assets\private" "data" "models" "backups" "__pycache__" /XF ".env" "*.log" "*.spec" >nul
if %ERRORLEVEL% GEQ 8 (
    echo [Daniya] Failed to copy PyInstaller output.
    pause
    exit /b 1
)

echo [Daniya] Copying public project files...
if not exist "release\!PACKAGE_NAME!\assets\placeholder" robocopy "assets\placeholder" "release\!PACKAGE_NAME!\assets\placeholder" /E >nul
if not exist "release\!PACKAGE_NAME!\assets\icons" robocopy "assets\icons" "release\!PACKAGE_NAME!\assets\icons" /E >nul
if not exist "release\!PACKAGE_NAME!\characters\daniya" robocopy "characters\daniya" "release\!PACKAGE_NAME!\characters\daniya" /E /XD "assets" >nul
if not exist "release\!PACKAGE_NAME!\characters\template" robocopy "characters\template" "release\!PACKAGE_NAME!\characters\template" /E >nul
if exist "release\!PACKAGE_NAME!\config" rmdir /s /q "release\!PACKAGE_NAME!\config"
robocopy "%SAFE_CONFIG%" "release\!PACKAGE_NAME!\config" /E >nul
if %ERRORLEVEL% GEQ 8 (
    echo [Daniya] Failed to copy public config files.
    pause
    exit /b 1
)
if exist "release\!PACKAGE_NAME!\docs" rmdir /s /q "release\!PACKAGE_NAME!\docs"
robocopy "%SAFE_DOCS%" "release\!PACKAGE_NAME!\docs" /E /XD "v0.51_patch_audit" "screenshots" "debug" "debug_logs" "tmp" "__pycache__" /XF "*.tmp" "*.log" "debug_*" >nul
if %ERRORLEVEL% GEQ 8 (
    echo [Daniya] Failed to copy public docs.
    pause
    exit /b 1
)
copy /Y "README.md" "release\!PACKAGE_NAME!\README.md" >nul
copy /Y "LICENSE" "release\!PACKAGE_NAME!\LICENSE" >nul
copy /Y "CHANGELOG.md" "release\!PACKAGE_NAME!\CHANGELOG.md" >nul
copy /Y ".env.example" "release\!PACKAGE_NAME!\.env.example" >nul
copy /Y "create_shortcut.bat" "release\!PACKAGE_NAME!\create_shortcut.bat" >nul

echo [Daniya] Removing forbidden package content if present...
if exist "release\!PACKAGE_NAME!\.env" del /q "release\!PACKAGE_NAME!\.env"
if exist "release\!PACKAGE_NAME!\config\api_config.json" del /q "release\!PACKAGE_NAME!\config\api_config.json"
if exist "release\!PACKAGE_NAME!\config\multimodal_config.json" del /q "release\!PACKAGE_NAME!\config\multimodal_config.json"
if exist "release\!PACKAGE_NAME!\assets\private" rmdir /s /q "release\!PACKAGE_NAME!\assets\private"
if exist "release\!PACKAGE_NAME!\data" rmdir /s /q "release\!PACKAGE_NAME!\data"
if exist "release\!PACKAGE_NAME!\models" rmdir /s /q "release\!PACKAGE_NAME!\models"
if exist "release\!PACKAGE_NAME!\backups" rmdir /s /q "release\!PACKAGE_NAME!\backups"
if exist "release\!PACKAGE_NAME!\docs\v0.51_patch_audit" rmdir /s /q "release\!PACKAGE_NAME!\docs\v0.51_patch_audit"
if exist "release\!PACKAGE_NAME!\docs\screenshots" rmdir /s /q "release\!PACKAGE_NAME!\docs\screenshots"
for /r "release\!PACKAGE_NAME!" %%F in (*.log *.spec *.broken-*) do del /q "%%F"
for /d /r "release\!PACKAGE_NAME!" %%D in (__pycache__) do rmdir /s /q "%%D" 2>nul

echo [Daniya] Creating zip package...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\!PACKAGE_NAME!' -DestinationPath 'release\!PACKAGE_NAME!.zip' -Force"
if errorlevel 1 (
    echo [Daniya] Zip creation failed.
    pause
    exit /b 1
)

echo [Daniya] Package complete:
echo [Daniya] release\!PACKAGE_NAME!\%APP_NAME%.exe
echo [Daniya] release\!PACKAGE_NAME!.zip
echo [Daniya] Private assets, .env, data, models, backups, build, and dist work directories are not included in the zip.
if exist "%PKG_STAGING%" rmdir /s /q "%PKG_STAGING%"
