FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (curl for healthchecks, iproute2 for tc/netem support in container)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy application source
COPY app/ ./app/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Expose API and Prometheus metrics ports
EXPOSE 8000 9090

# Default command runs FastAPI via uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
