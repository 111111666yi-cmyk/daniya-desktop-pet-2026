@echo off
chcp 65001 >nul
echo [Daniya] Creating desktop shortcut "达妮娅桌宠"...

:: Path auto-detection
set "EXE_PATH=%~dp0DaniyaSummerPet.exe"

if not exist "%EXE_PATH%" (
    set "EXE_PATH=%~dp0dist\DaniyaSummerPet\DaniyaSummerPet.exe"
)

if not exist "%EXE_PATH%" (
    set "EXE_PATH=%~dp0release\DaniyaSummerPet-v0.49-win-x64\DaniyaSummerPet.exe"
)

if not exist "%EXE_PATH%" (
    echo [Daniya] Error: DaniyaSummerPet.exe not found!
    echo Please make sure this script is placed in the extracted folder with DaniyaSummerPet.exe.
    pause
    exit /b 1
)

set "TEMP_PS=%TEMP%\daniya_shortcut.ps1"
echo $WshShell = New-Object -ComObject WScript.Shell > "%TEMP_PS%"
echo $Shortcut = $WshShell.CreateShortcut([System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), '达妮娅桌宠.lnk')) >> "%TEMP_PS%"
echo $Shortcut.TargetPath = '%EXE_PATH%' >> "%TEMP_PS%"
echo $Shortcut.WorkingDirectory = '%~dp0' >> "%TEMP_PS%"
echo $Shortcut.IconLocation = '%~dp0assets\placeholder\app.ico' >> "%TEMP_PS%"
echo $Shortcut.Save() >> "%TEMP_PS%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP_PS%"
del "%TEMP_PS%"

echo [Daniya] Shortcut "达妮娅桌宠" created successfully on your Desktop!
pause
