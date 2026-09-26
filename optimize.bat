@echo off
REM One-click launcher for Windows. Usage: optimize.bat [command] [options]
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import psutil" 2>nul || %PY% -m pip install --user -q -r requirements.txt
%PY% -m optimizer %*
if "%~1"=="" pause
