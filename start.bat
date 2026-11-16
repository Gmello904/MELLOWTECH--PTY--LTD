@echo off
setlocal
cd /d "%~dp0backend"
set PY=python
where python >nul 2>nul || set PY=py
echo Using: %PY%
echo Checking required packages (flask, psutil)...
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo Could not install the packages. Read the message above.
    pause
    exit /b 1
)
echo.
echo Starting MellowTech. Keep this window open while you use the site.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000/"
%PY% app.py
echo.
echo The server has stopped. Read the message above to see why.
pause
