@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python server.py) else (py server.py)
pause
