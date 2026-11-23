@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Lance d'abord build_exe.bat pour installer les dependances.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
