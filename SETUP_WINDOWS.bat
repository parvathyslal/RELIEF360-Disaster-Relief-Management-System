@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -m pip install -r requirements.txt
if errorlevel 1 goto finish
py setup_database.py
goto finish
:use_python
python -m pip install -r requirements.txt
if errorlevel 1 goto finish
python setup_database.py
:finish
pause
