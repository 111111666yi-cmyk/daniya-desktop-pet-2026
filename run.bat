@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Daniya] Virtual environment not found. Please run install.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" main.py
