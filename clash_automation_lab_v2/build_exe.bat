@echo off
setlocal
cd /d "%~dp0"
echo Installing app and packaging dependencies...
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error
echo Building Clash Automation Lab...
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name ClashAutomationLab main.py
if errorlevel 1 goto error
echo.
echo Build finished. Run dist\ClashAutomationLab\ClashAutomationLab.exe
echo Keep profiles.db beside the EXE to preserve your settings and tasks.
pause
goto end
:error
echo.
echo Build failed. Read the error messages above.
pause
:end
endlocal
