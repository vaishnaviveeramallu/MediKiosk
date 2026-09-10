# MediKiosk - MongoDB Setup and Runner Script
param(
    [switch]$Foreground = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$MongoBinDir = Join-Path $ProjectRoot "mongodb-bin"
$DataDbDir = Join-Path $ProjectRoot "data\db"
$ZipPath = Join-Path $ProjectRoot "mongodb.zip"

Write-Host "=== MediKiosk MongoDB Initialization ===" -ForegroundColor Cyan

# 1. Ensure data directory exists
if (-not (Test-Path $DataDbDir)) {
    New-Item -ItemType Directory -Force -Path $DataDbDir | Out-Null
    Write-Host "Created database storage directory at: $DataDbDir" -ForegroundColor Gray
}

# 2. Find mongod.exe
$mongodPath = Join-Path $MongoBinDir "bin\mongod.exe"
if (-not (Test-Path $mongodPath)) {
    # Check if inside an extracted subfolder e.g. mongodb-bin\mongodb-win32-x86_64-windows-7.0.14\bin\mongod.exe
    $found = Get-ChildItem -Path $MongoBinDir -Filter "mongod.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $mongodPath = $found.FullName
    }
}

if (-not (Test-Path $mongodPath)) {
    if (Test-Path $ZipPath) {
        Write-Host "Extracting $ZipPath into $MongoBinDir ..." -ForegroundColor Yellow
        Expand-Archive -Path $ZipPath -DestinationPath $MongoBinDir -Force
        $found = Get-ChildItem -Path $MongoBinDir -Filter "mongod.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $mongodPath = $found.FullName
        }
    }
}

# If still not found, check system PATH
if (-not (Test-Path $mongodPath)) {
    $sysMongod = Get-Command "mongod" -ErrorAction SilentlyContinue
    if ($sysMongod) {
        $mongodPath = $sysMongod.Source
    }
}

if (-not (Test-Path $mongodPath)) {
    Write-Error "mongod.exe could not be found. Please ensure mongodb.zip has finished downloading."
    exit 1
}

Write-Host "Found MongoDB binary at: $mongodPath" -ForegroundColor Green

# 3. Check if MongoDB is already listening on port 27017
$tcpTest = Test-NetConnection -ComputerName 127.0.0.1 -Port 27017 -WarningAction SilentlyContinue
if ($tcpTest.TcpTestSucceeded) {
    Write-Host "MongoDB is already running and listening on 127.0.0.1:27017." -ForegroundColor Green
    exit 0
}

Write-Host "Starting mongod on 127.0.0.1:27017 (dbpath: $DataDbDir)..." -ForegroundColor Cyan

$logPath = Join-Path $ProjectRoot "data\mongod.log"
$argsList = @(
    "--dbpath", "`"$DataDbDir`"",
    "--port", "27017",
    "--bind_ip", "127.0.0.1",
    "--logpath", "`"$logPath`"",
    "--logappend"
)

$process = Start-Process -FilePath $mongodPath -ArgumentList ($argsList -join " ") -PassThru -WindowStyle Hidden

Write-Host "Launched mongod process (PID: $($process.Id)). Verifying connectivity..." -ForegroundColor Yellow

# 4. Wait for connectivity
$attempts = 0
$maxAttempts = 30
$connected = $false

while ($attempts -lt $maxAttempts) {
    Start-Sleep -Seconds 1
    $attempts++
    $check = Test-NetConnection -ComputerName 127.0.0.1 -Port 27017 -WarningAction SilentlyContinue
    if ($check.TcpTestSucceeded) {
        $connected = $true
        break
    }
}

if ($connected) {
    Write-Host "Successfully connected to MongoDB on port 27017!" -ForegroundColor Green
} else {
    Write-Error "Timed out waiting for MongoDB to start. Check log at: $logPath"
    exit 1
}
