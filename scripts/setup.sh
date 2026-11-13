#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "   Chaos Probe - Microservices Resilience Testing Platform"
echo "   Automated Setup & Environment Bootstrapper"
echo "=========================================================="

# Check Python version
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3.12+ is required but python3 was not found in PATH." >&2; exit 1; }
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[1/5] Detected Python version: ${PYTHON_VERSION}"

# Create or reuse virtualenv
if [ ! -d ".venv" ]; then
    echo "[2/5] Creating Python virtual environment in .venv..."
    python3 -m venv .venv
else
    echo "[2/5] Existing .venv detected."
fi

# Source virtualenv
source .venv/bin/activate || source .venv/Scripts/activate

# Upgrade pip and install package
echo "[3/5] Installing dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Configure .env if missing
if [ ! -f ".env" ]; then
    echo "[4/5] Copying .env.example to .env..."
    cp .env.example .env
else
    echo "[4/5] .env file already exists."
fi

# Run database migrations and seed data
echo "[5/5] Running database migrations and seed data..."
alembic upgrade head || python -c "from app.database.base import Base; from app.database.session import engine; Base.metadata.create_all(bind=engine)"
python scripts/seed_data.py

echo ""
echo "=========================================================="
echo " Setup complete!"
echo " To run the API locally:"
echo "     source .venv/bin/activate (or .venv/Scripts/activate)"
echo "     uvicorn app.main:app --reload --port 8000"
echo ""
echo " Or to launch the entire stack with Docker Compose:"
echo "     docker compose up --build"
echo ""
echo " API Docs:    http://localhost:8000/docs"
echo " Prometheus:  http://localhost:9090"
echo " Grafana:     http://localhost:3000 (admin / admin)"
echo "=========================================================="
