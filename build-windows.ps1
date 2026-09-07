$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:npm_config_cache = Join-Path $PSScriptRoot '.npm-cache'
Write-Host '============================================================'
Write-Host '         FIREFLIES CLONE - WINDOWS APP BUILDER'
Write-Host '============================================================'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 22+ is required.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm is required.' }
$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($python) { $pyCmd = 'py -3.11' } else { $pyCmd = 'python' }

if (-not (Test-Path 'frontend/node_modules')) {
  Push-Location frontend; npm install --no-package-lock --no-audit --no-fund; Pop-Location
}
Push-Location frontend; npm run build; Pop-Location

if (-not (Test-Path '.venv')) {
  cmd /c "$pyCmd -m venv .venv"
  if ($LASTEXITCODE -ne 0) { python -m venv .venv }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt pyinstaller
if (Test-Path 'backend/dist') { Remove-Item 'backend/dist' -Recurse -Force }
if (Test-Path 'backend/build') { Remove-Item 'backend/build' -Recurse -Force }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --name fireflies-backend --paths backend --hidden-import app.main --collect-submodules fastapi --collect-submodules uvicorn --collect-submodules sqlalchemy --collect-submodules pydantic backend\launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }

npm install --no-package-lock --no-audit --no-fund
npx electron-builder --win nsis --x64
if ($LASTEXITCODE -ne 0) { throw 'Electron packaging failed.' }
Write-Host "`nInstaller is in .\release\"
