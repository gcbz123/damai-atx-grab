@echo off
chcp 65001 >nul
cd /d "%~dp0.."
python scripts\dump_page_xml.py
pause
