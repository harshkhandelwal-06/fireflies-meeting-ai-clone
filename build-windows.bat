@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "npm_config_cache=%CD%\.npm-cache"

echo ==============================================
echo Fireflies Clone - 2.4.2 WINDOWS BUILD
 echo ==============================================

where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js is not installed.
  echo Install Node.js 22 LTS or newer, then run this script again.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm is not installed.
  pause
  exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher is not installed.
  pause
  exit /b 1
)

py -3.11 -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 is required for the backend build.
  pause
  exit /b 1
)

echo [1/4] Installing frontend dependencies...
cd frontend
call npm install --no-package-lock --no-audit --no-fund
if errorlevel 1 goto :fail

echo [2/4] Building the production frontend...
call npm run build
if errorlevel 1 goto :fail
if not exist out\index.html ( echo ERROR: frontend\out\index.html was not generated. & goto :fail )
cd ..

echo [3/4] Building the bundled backend executable...
call desktop\build-backend.bat
if errorlevel 1 goto :fail

echo [4/4] Packaging Windows portable EXE and installer...
call npm install --no-package-lock --no-audit --no-fund
if errorlevel 1 goto :fail
call npx electron-builder --win portable nsis --x64 --publish never
if errorlevel 1 goto :fail

echo.
echo ==============================================
echo BUILD COMPLETE
 echo ==============================================
echo.
echo Portable application:
echo   release\Fireflies-Clone-Portable-2.4.2.exe
echo.
echo Installer:
echo   release\Fireflies-Clone-2.4.2-x64.exe
echo.
echo The evaluator only needs the finished EXE.
echo They do NOT need Node.js, Python, npm, or localhost.
echo.
pause
exit /b 0

:fail
cd /d "%~dp0"
echo.
echo BUILD FAILED. Read the error above.
pause
exit /b 1
