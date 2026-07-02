@echo off
title Damai ATX Grab GUI

cd /d "%~dp0.."

echo Starting Damai ATX Grab GUI...
echo.

python -m src.main_gui

echo.
echo GUI exited.
pause
