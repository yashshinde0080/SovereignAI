@echo off
setlocal
title SovereignAI Edge - Web
cd /d "%~dp0"

:: Start backend in its own window
echo [INFO] Starting backend...
start "Backend" cmd /k "cd backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Start frontend in its own window
echo [INFO] Starting frontend...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo [OK] Both started. Close windows to stop.
