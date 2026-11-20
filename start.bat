@echo off
setlocal
cd /d "%~dp0"
python app.py --host 127.0.0.1 --port 8765 --config config.json
if errorlevel 1 pause

