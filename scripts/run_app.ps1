# MediKiosk - Master Runner Script
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "       Starting MediKiosk Healthcare Platform   " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."

# 1. Start MongoDB
Write-Host "[1/3] Starting MongoDB database..." -ForegroundColor Yellow
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\setup_and_run_db.ps1"

# 2. Start Backend
Write-Host "[2/3] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Yellow
$backendEnv = @{
    PYTHONPATH = "$ProjectRoot\backend"
}
Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory "$ProjectRoot\backend" -WindowStyle Minimized

# 3. Start Frontend
Write-Host "[3/3] Starting Next.js Kiosk UI on http://localhost:3000 ..." -ForegroundColor Yellow
$nodeDir = "C:\Users\Veeramallu Jayanth\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
$npmCmd = Join-Path $nodeDir "npm.cmd"
Start-Process -FilePath $npmCmd -ArgumentList "run start" -WorkingDirectory "$ProjectRoot\frontend" -WindowStyle Minimized

Write-Host "`nAll MediKiosk services are running!" -ForegroundColor Green
Write-Host "  - Kiosk Frontend:   http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - Patient Register: http://localhost:3000/register" -ForegroundColor Cyan
Write-Host "  - OPD Live Queue:   http://localhost:3000/queue" -ForegroundColor Cyan
Write-Host "  - Backend API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
