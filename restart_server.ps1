#!/usr/bin/env pwsh
# Force restart server with cache clearing

Write-Host "Stopping Python processes..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like '*python*'} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Clearing __pycache__ directories..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Clearing .pyc files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

Write-Host "Starting server..." -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8008
