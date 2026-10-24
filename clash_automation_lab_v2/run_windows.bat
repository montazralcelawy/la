@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto error
py -3 main.py
if errorlevel 1 goto error
goto end
:error
echo.
echo An error occurred. Check that Python 3.11+ is installed and available as py.
pause
:end
endlocal
