@echo off
setlocal EnableExtensions
cd /d "%~dp0..\backend"

if not exist .venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3.11 -m venv .venv
  )
  if errorlevel 1 (
    echo ERROR: Python 3.11 is required.
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean --onefile --name fireflies-backend --distpath dist --workpath build --specpath build launcher.py
if errorlevel 1 exit /b 1

if not exist dist\fireflies-backend.exe (
  echo ERROR: Backend executable was not created.
  exit /b 1
)

cd /d "%~dp0.."
echo Backend executable created successfully.
