@echo off
title XML Transform
cd /d "%~dp0"

REM Prefer venv if present
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" xml_xslt_gui.py 2>nul
if errorlevel 1 (
  py xml_xslt_gui.py 2>nul
)
if errorlevel 1 (
  echo.
  echo Could not start the app. Install Python and dependencies:
  echo   pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

exit /b 0
