 @echo off
setlocal
cd /d "%~dp0backend"
set PY=python
where python >nul 2>nul || set PY=py
set /p ROc:\Users\Given\AppData\Local\Temp\add-user.batLE=Role for the new user (admin or viewer): 
%PY% app.py create-user %ROLE%
echo.c:\Users\Given\Ac:\Users\Given\AppData\Local\Temp\add-user (2).batppData\Local\Temp\add-user (1).bat
pause