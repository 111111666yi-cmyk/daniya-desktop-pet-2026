@echo off
chcp 65001 >nul
echo =====================================================
echo           达妮娅桌宠项目 - Windows 系统自动化修复
echo =====================================================
echo.
echo 正在请求管理员权限以运行修复脚本...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0scratch\automated_system_repair.ps1\"' -Verb RunAs"

if %errorlevel% neq 0 (
    echo [错误] 启动失败，请确保您在弹出的 UAC 提示中选择“是”。
    pause
)
