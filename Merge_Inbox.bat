@echo off
cd /d "%~dp0.."
python _tools\merge_inbox.py
echo.
pause
