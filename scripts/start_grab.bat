@echo off
title Damai Ticket Grabber v2.0

echo ============================================
echo   Damai ATX Grab v2.0
echo ============================================
echo.

cd /d "%~dp0.."

if not exist config.jsonc (
    echo [ERROR] config.jsonc not found
    pause
    exit /b 1
)

echo Select mode:
echo   1 - Probe mode (default, no click)
echo   2 - Dry-run mode (stop before submit)
echo   3 - Live mode (submit order)
echo.

set /p mode="Enter [1/2/3]: "

if "%mode%"=="2" (
    set extra=--no-probe-only
) else if "%mode%"=="3" (
    set extra=--commit
) else (
    set extra=
)

echo.
echo Starting...
echo.

python -m src.main %extra%

echo.
echo Done. Press any key to exit...
pause >nul
