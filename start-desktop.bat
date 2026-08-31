@echo off
setlocal
title SovereignAI Edge - Desktop
cd /d "%~dp0"

:: Start backend in its own window
echo [INFO] Starting backend...
start "Backend" cmd /k "cd backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Start Electron in its own window
echo [INFO] Starting Electron...
start "Electron" cmd /k "cd electron && npm run dev"

echo [OK] Both started. Close windows to stop.
