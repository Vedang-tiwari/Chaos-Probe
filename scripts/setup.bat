@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    Chaos Probe - Microservices Resilience Testing Platform
echo    Windows Automated Setup Bootstrapper
echo ==========================================================

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3.12+ was not found in PATH.
    exit /b 1
)

echo [1/5] Checking Python environment...
python --version

REM Virtual environment setup
if not exist ".venv" (
    echo [2/5] Creating virtual environment .venv...
    python -m venv .venv
) else (
    echo [2/5] Existing .venv directory found.
)

call .venv\Scripts\activate.bat

echo [3/5] Installing project dependencies...
python -m pip install --upgrade pip
pip install -e .[dev]

REM Configure .env
if not exist ".env" (
    echo [4/5] Creating .env from .env.example...
    copy .env.example .env >nul
) else (
    echo [4/5] .env file already exists.
)

REM Initialize DB and seed data
echo [5/5] Running schema setup and database seed...
python -c "from app.database.base import Base; from app.database.session import engine; Base.metadata.create_all(bind=engine)"
python scripts/seed_data.py

echo.
echo ==========================================================
echo  Setup complete!
echo  To run the API locally:
echo      call .venv\Scripts\activate
echo      uvicorn app.main:app --reload --port 8000
echo.
echo  Or to launch the full Docker Compose stack:
echo      docker compose up --build
echo.
echo  API Documentation: http://localhost:8000/docs
echo  Prometheus:        http://localhost:9090
echo  Grafana:           http://localhost:3000 (admin / admin)
echo ==========================================================

