@echo off
setlocal enabledelayedexpansion

:: SovereignAI Edge Launcher for Windows

title SovereignAI Edge

echo.
echo ╔═══════════════════════════════════════╗
echo ║       SovereignAI Edge v1.0.0         ║
echo ║   Portable Offline AI Platform        ║
echo ╚═══════════════════════════════════════╝
echo.

:: Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is required but not installed.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% found

:: Check/create virtual environment
set "VENV_DIR=%SCRIPT_DIR%.venv"

if not exist "%VENV_DIR%" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

:: Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

:: Install dependencies if needed
if not exist "%VENV_DIR%\.installed" (
    echo [INFO] Installing dependencies...
    pip install --upgrade pip
    pip install -r "%SCRIPT_DIR%backend\requirements.txt"
    echo. > "%VENV_DIR%\.installed"
)

echo [OK] Dependencies installed

:: Resolve host:port from the settings DB (security.api_port / bind_localhost_only)
set "API_ADDR=127.0.0.1:8000"
for /f "usebackq tokens=*" %%i in (`python -c "import sys; sys.path.insert(0, 'backend'); from main import get_server_config; h, p = get_server_config(); h = '127.0.0.1' if h == '0.0.0.0' else h; print(f'{h}:{p}')" 2^>nul`) do set "API_ADDR=%%i"
for /f "tokens=2 delims=:" %%p in ("!API_ADDR!") do set "API_PORT=%%p"
echo [OK] API will listen on !API_ADDR!

:: Create necessary directories (all runtime storage lives in workspace/)
if not exist "%SCRIPT_DIR%workspace\sessions" mkdir "%SCRIPT_DIR%workspace\sessions"
if not exist "%SCRIPT_DIR%workspace\documents" mkdir "%SCRIPT_DIR%workspace\documents"
if not exist "%SCRIPT_DIR%workspace\logs" mkdir "%SCRIPT_DIR%workspace\logs"
if not exist "%SCRIPT_DIR%workspace\plugins" mkdir "%SCRIPT_DIR%workspace\plugins"

:: Check if the configured port is already in use
netstat -ano | findstr :%API_PORT% >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARN] Port %API_PORT% is already in use
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') do (
        echo [INFO] Stopping existing process %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 >nul
)

:: Start backend (honors settings DB: security.api_port, security.bind_localhost_only)
echo [INFO] Starting backend server...
cd /d "%SCRIPT_DIR%backend"

start /b python main.py

:: Wait for backend
echo [INFO] Waiting for backend...
:wait_loop
timeout /t 1 >nul
curl -s http://!API_ADDR!/health >nul 2>&1
if %errorlevel% neq 0 goto wait_loop

echo [OK] Backend is ready

echo.
echo ═══════════════════════════════════════
echo SovereignAI Edge is running!
echo.
echo   API:  http://!API_ADDR!
echo   Docs: http://!API_ADDR!/docs
echo.
echo   CLI:  sovereign --help   (or: cd backend\app ^&^& python -m cli.main --help)
echo.
echo ═══════════════════════════════════════
echo.
echo Press Ctrl+C to stop
echo.

:: Open browser (optional)
:: start http://127.0.0.1:8000/docs

:: Keep window open
:loop
timeout /t 60 >nul
goto loop