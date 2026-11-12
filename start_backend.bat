@echo off
cd /d "%~dp0backend"
call .venv\Scripts\activate
REM --reload-dir app keeps WatchFiles off .venv/.python: importing torch on
REM model load touched site-packages and reloaded the server mid-request.
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
