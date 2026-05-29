@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.13+ is required but was not found in PATH.
    exit /b 1
)

python --version

if not exist ".venv" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

if not "%LAITOXX_INSTALL_PLANET%"=="" (
    set "LAITOXX_INSTALL_GEOCLIP=%LAITOXX_INSTALL_PLANET%"
)
if "%LAITOXX_INSTALL_GEOCLIP%"=="" (
    set /p LAITOXX_INSTALL_GEOCLIP=Install optional PlaNet-like/GeoCLIP Photo Geolocation mode? [y/N] 
)
if /i "%LAITOXX_INSTALL_GEOCLIP%"=="y" (
    echo Installing optional PlaNet-like/GeoCLIP dependencies...
    python -m pip install -r requirements-photo2geo-geoclip.txt
)

where nmap >nul 2>nul
if errorlevel 1 (
    echo Warning: nmap was not found in PATH. Install Nmap to use the Nmap tool.
    echo Windows: install from https://nmap.org/download.html or use winget/choco.
) else (
    for /f "delims=" %%i in ('where nmap') do echo Nmap found: %%i
)

echo Installation complete. Run: .venv\Scripts\activate.bat ^&^& python cli.py
endlocal
