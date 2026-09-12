@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
 python -m venv .venv
 .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist ".env" copy ..\.env.example .env
.venv\Scripts\python.exe -m uvicorn main:app --reload
pause
