@echo off
REM scripts\launch.bat

set SOVEREIGN_ROOT=%~dp0..
cd /d %SOVEREIGN_ROOT%

if not exist "bin\sovereign-runtime.exe" (
    echo Building SovereignAI...
    cargo build --release
    if not exist "bin" mkdir bin
    copy target\release\sovereign-ai.exe bin\sovereign-runtime.exe
    copy target\release\sovereign-ai.exe bin\sovereign-cli.exe
)

echo ========================================
echo   SovereignAI Edge v0.1.0
echo   Portable Offline LLM Runtime
echo ========================================

bin\sovereign-runtime.exe %*