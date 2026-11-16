@echo off
rem Builds MellowTechAgent.exe (Windows). Run once on a Windows PC that has Python 3. Result: dist\MellowTechAgent.exe
rem Put that file in the "agent" folder next to your site so the Download button works.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller psutil
python -m PyInstaller --onefile --name MellowTechAgent --hidden-import psutil mellowtech_agent.py
echo.
echo Done. Your file is: %~dp0dist\MellowTechAgent.exe
pause