# Chaos Probe ⚡

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-container--isolated-2496ED.svg)](https://www.docker.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-ready-E6522C.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-dashboard-F46800.svg)](https://grafana.com/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-35%20passed-brightgreen.svg)](tests/)

**Chaos Probe** is an enterprise-grade, controlled fault-injection and resilience testing platform engineered specifically for containerized microservices and distributed systems. It enables engineering teams to empirically validate system survival, latency degradation, error rates, and automatic recovery under real-world catastrophic failure modes—before outages strike production.

---

## 📋 Table of Contents
1. [Core Mission & Capabilities](#-core-mission--capabilities)
2. [High-Level Architecture](#-high-level-architecture)
3. [Experiment Lifecycle State Machine](#-experiment-lifecycle-state-machine)
4. [Fault Injection Catalog](#-fault-injection-catalog)
5. [Safety System & Guardrails](#-safety-system--guardrails)
6. [Resilience Scoring Model (0–100)](#-resilience-scoring-model-0100)
7. [Reporting Engine (JSON & Interactive HTML)](#-reporting-engine-json--interactive-html)
8. [Observability Stack (Prometheus & Grafana)](#-observability-stack-prometheus--grafana)
9. [Quick Start & Setup](#-quick-start--setup)
10. [Sample Experiments Walkthrough](#-sample-experiments-walkthrough)
11. [Complete REST API Reference](#-complete-rest-api-reference)
12. [Testing & Verification](#-testing--verification)
13. [Project Directory Layout](#-project-directory-layout)

---

## 🎯 Core Mission & Capabilities

Modern microservices architectures feature hidden cascading failure paths that traditional unit, integration, and load tests cannot expose. **Chaos Probe** deliberately subjects target services to controlled chaos:

- **Network Instability**: Simulates transient carrier latency, jitter, packet loss, and link flaps.
- **Resource Starvation**: Restricts host CPU cycles and memory allocations via cgroups without killing the host.
- **Hard Crashes**: Terminates and restarts target containers to measure failover time and cold-boot recovery.
- **Cascading HTTP Failures**: Simulates upstream `503 Service Unavailable` storms and unhandled gateway timeouts.
- **Deterministic Resilience Scoring**: Quantifies system survival on an objective 0–100 scale.
- **Automated Recommendations**: Generates concrete architectural remediation guidance (circuit breakers, retry backoffs, connection timeouts).

---

## 🏛️ High-Level Architecture

Chaos Probe is designed around strict separation of concerns, pluggable adapters, and zero unmanaged side effects:

```
                                  +---------------------------------------+
                                  |     Chaos Probe Client / CLI / UI     |
                                  +---------------------------------------+
                                                      |
                                                      v
                                        +---------------------------+
                                        |  FastAPI Gateway & Auth   |
                                        |     (:8000 /api/v1)       |
                                        +---------------------------+
                                          /           |           \
                                         /            |            \
                 +----------------------+             |             +-----------------------+
                 |   Service Registry   |             |             |   Safety Controller   |
                 | (Health Probes & DB) |             |             | (Locks & Guardrails)  |
                 +----------------------+             |             +-----------------------+
                                                      v
                                        +---------------------------+
                                        |   Experiment Executor     |
                                        |    (10-State Machine)     |
                                        +---------------------------+
                                          /           |           \
                                         /            |            \
              +-------------------------+             |             +-------------------------+
              |   Chaos Strategy Engine |             |             |    Metrics Collector    |
              | (Docker API / tc netem) |             |             |  (Prometheus Exporter)  |
              +-------------------------+             |             +-------------------------+
                                                      v
                                        +---------------------------+
                                        |  Analysis & Scoring       |
                                        | (0-100 Score & Recs)      |
                                        +---------------------------+
                                                      |
                                                      v
                                        +---------------------------+
                                        |     Reporting Engine      |
                                        |   (JSON & HTML Reports)   |
                                        +---------------------------+
```

### Core Components
1. **Service Registry (`app/services/service_registry.py`)**: Stores target services, container bindings, URLs, and active health check statuses.
2. **Safety Controller (`app/chaos/safety_controller.py`)**: Enforces concurrency locks (one active chaos test per target), global duration limits, and automatic circuit-breaking guardrails.
3. **Execution Engine (`app/chaos/executor.py`)**: Drives the strict 10-state experiment lifecycle with guaranteed rollback hooks.
4. **Fault Strategy Registry & Adapters (`app/chaos/`)**: Pluggable strategies interacting with Docker containers and Linux networking tools (`tc netem`, `stress-ng`, cgroups).
5. **Observability Pipeline (`app/monitoring/`)**: Continuous sampling of latency, error rate, and availability into Prometheus gauges and histograms.
6. **Resilience Analyzer (`app/analysis/`)**: Multi-pillar deterministic scoring with automated grade assignment.
7. **Reporting Engine (`app/reports/`)**: Generates structured JSON summaries and interactive HTML report dashboards.

---

## 🔄 Experiment Lifecycle State Machine

Every experiment progresses through an auditable, deterministic 10-state lifecycle:

```
  [CREATED]
      │
      ▼
[VALIDATING] ──────── (Target unhealthy / locked) ─────────► [FAILED]
      │
      ▼
[BASELINE_COLLECTION] (Samples pre-fault latency & availability)
      │
      ▼
  [RUNNING]
      │
      ▼
[FAULT_INJECTED] ──── (Safety guardrail breached) ─────────► [ABORTED]
      │                                                           │
      ▼                                                           │
 [OBSERVING] ──────── (Emergency stop triggered) ─────────────────┤
      │                                                           │
      ▼                                                           │
 [RECOVERING] ◄───────────────────────────────────────────────────┘
      │
      ├────► Target fully recovered  ──────► [COMPLETED]
      │
      └────► Target recovery timeout ──────► [FAILED]
```

At every state, if an unexpected error or operator abort occurs, the **Rollback Manager** is guaranteed to execute, restoring target containers and network configurations to clean baseline states.

---

## ⚡ Fault Injection Catalog

Chaos Probe includes 7 fault injection strategies out of the box:

| Strategy | Identifier | Target Layer | Configurable Parameters | Description |
|---|---|---|---|---|
| **Network Latency** | `network_latency` | Network | `latency_ms`, `jitter_ms`, `correlation_percent` | Injects synthetic delay into container network interfaces using `tc qdisc netem`. |
| **Packet Loss** | `packet_loss` | Network | `loss_percent`, `correlation_percent` | Emulates dropped packets to evaluate TCP retransmission and timeout resiliency. |
| **CPU Stress** | `cpu_stress` | Compute | `cpu_percent`, `workers`, `timeout_seconds` | Throttles CPU or spawns compute workers to saturate target container execution threads. |
| **Memory Pressure** | `memory_pressure` | Memory | `size_mb`, `workers` | Allocates active memory chunks to test container OOM recovery and memory reclamation. |
| **Container Termination**| `container_kill` | Process | `action` (`stop`, `kill`, `restart`), `timeout_seconds` | Simulates sudden process termination or cold restarts to verify failover handling. |
| **Service Unavailability**| `service_unavailable` | Application | `error_code` (e.g. 503), `error_ratio` | Forces intermittent or constant HTTP 5xx responses from the service layer. |
| **Request Timeout** | `request_timeout` | Network/App | `timeout_seconds`, `error_ratio` | Delays HTTP request handling until client or gateway read timeouts trigger. |

---

## 🛡️ Safety System & Guardrails

Chaos engineering must never cause uncontained damage. Chaos Probe enforces multi-layer defense in depth:

1. **Target Concurrency Locking**: Prevents overlapping experiments on the same target service.
2. **Hard Parameter Bounds**:
   - Experiment duration capped at 300 seconds maximum (default recommendation: 30s).
   - CPU stress capped at 95%.
   - Latency injections capped at 10,000ms.
3. **Runtime Guardrails**: Continuous monitoring during fault injection:
   - `max_error_rate`: Aborts if error rate exceeds threshold (e.g. > 25%).
   - `max_latency_ms`: Aborts if average response latency spikes past threshold (e.g. > 3,000ms).
   - `min_availability`: Aborts if target availability drops below threshold (e.g. < 70%).
4. **Idempotent Guaranteed Rollback**: Rollback routines are executed in `finally` blocks, tracking any failed rollbacks in an administrative unhealthy cleanups queue.
5. **Instant Emergency Stop**: `POST /api/v1/admin/emergency-stop` terminates all active experiments immediately and restores all containers.

---

## 📊 Resilience Scoring Model (0–100)

Chaos Probe calculates a deterministic resilience score from four weighted operational dimensions:

$$\text{Resilience Score} = (S_{\text{avail}} \times 0.35) + (S_{\text{error}} \times 0.25) + (S_{\text{latency}} \times 0.20) + (S_{\text{recovery}} \times 0.20)$$

### 1. Availability Score ($S_{\text{avail}}$, 35% Weight)
Measures the percentage of health probes that returned a successful status code during the fault injection phase:
$$S_{\text{avail}} = \text{availability\_percentage} \quad (0 - 100)$$

### 2. Error Rate Score ($S_{\text{error}}$, 25% Weight)
Penalizes failed HTTP probes (non-2xx/3xx codes and connection dropouts):
$$S_{\text{error}} = \max(0, 100 - (\text{error\_rate} \times 100))$$

### 3. Latency Degradation Score ($S_{\text{latency}}$, 20% Weight)
Evaluates response time inflation during the fault compared to pre-fault baseline:
- $\le 100\%$ degradation $\rightarrow 100$
- $100\% - 300\%$ degradation $\rightarrow 75$
- $300\% - 500\%$ degradation $\rightarrow 50$
- $> 500\%$ degradation $\rightarrow 25$

### 4. Recovery Performance Score ($S_{\text{recovery}}$, 20% Weight)
Quantifies how rapidly the service returns to healthy baseline after the fault is rolled back:
- Recovery $\le 2\text{s} \rightarrow 100$
- Recovery $2\text{s} - 5\text{s} \rightarrow 80$
- Recovery $5\text{s} - 15\text{s} \rightarrow 60$
- Recovery $15\text{s} - 30\text{s} \rightarrow 30$
- Recovery failure or $> 30\text{s} \rightarrow 0$

### Grade Thresholds
| Grade | Score Range | Operational Meaning |
|---|---|---|
| **A (Excellent)** | 90.0 – 100.0 | High resilience; gracefully absorbs failures with negligible degradation. |
| **B (Good)** | 75.0 – 89.9 | Good resilience; minor degradation with rapid automatic recovery. |
| **C (Fair)** | 60.0 – 74.9 | Noticeable performance degradation; tuning needed for retries and timeouts. |
| **D (Poor)** | 40.0 – 59.9 | Severe degradation or slow recovery; cascading failure risk. |
| **F (Critical)**| 0.0 – 39.9 | Complete service failure without automatic recovery; urgent remediation required. |

---

## 📑 Reporting Engine (JSON & Interactive HTML)

Chaos Probe automatically persists structured reports upon experiment completion:

- **JSON Endpoint (`GET /api/v1/experiments/{id}/report`)**: Machine-readable format containing full execution metadata, metrics aggregates, breakdown scores, and prioritized remediation actions.
- **Interactive HTML Dashboard (`GET /api/v1/experiments/{id}/report.html`)**: Responsive, standalone web dashboard featuring:
  - Hero header with Letter Grade and 0–100 score badge
  - Timeline of lifecycle events
  - Key Metrics cards (Availability, Baseline vs Fault vs Recovery Latency, Error Rate)
  - Color-coded Architectural Remediation Recommendations
- **Historical Service Comparison (`GET /api/v1/experiments/compare/{service_id}`)**: Compares multiple chaos runs over time to track resilience trendlines across deployments.

---

## 📈 Observability Stack (Prometheus & Grafana)

Chaos Probe exposes first-class Prometheus metrics at `GET /metrics`:

| Metric Name | Type | Description |
|---|---|---|
| `chaos_probe_experiments_total` | Counter | Total experiments run, partitioned by `fault_type` and `status` |
| `chaos_probe_experiments_running` | Gauge | Currently active running experiments |
| `chaos_probe_service_availability` | Gauge | Real-time target service availability (0.0 to 1.0) |
| `chaos_probe_service_latency_seconds` | Histogram | Probe latency by `service` and `phase` (`baseline`, `fault`, `recovery`) |
| `chaos_probe_service_error_rate` | Gauge | Error rate ratio during experiment observation |
| `chaos_probe_active_faults` | Gauge | Current number of active faults injected by strategy |
| `chaos_probe_recovery_duration_seconds` | Histogram | Seconds taken for target to return to healthy baseline |

### Pre-provisioned Grafana Dashboard
A complete Grafana dashboard (`monitoring/grafana/dashboards/chaos_probe_overview.json`) is automatically provisioned in Docker Compose:
- **Active Running Experiments Counter**
- **Target Availability Gauges**
- **Experiment Phase Latency Distribution Graphs**
- **Error Rate & Outage Indicators**
- **Service Resilience Score History**

---

## 🚀 Quick Start & Setup

### Option 1: Full Stack with Docker Compose (Recommended)

Starts the entire environment: PostgreSQL, Redis, Chaos Probe API, Prometheus, Grafana, and a sample target service.

```bash
docker compose up --build -d
```

Service URLs:
- **Chaos Probe API & Docs**: `http://localhost:8000/docs`
- **Prometheus UI**: `http://localhost:9090`
- **Grafana Dashboard**: `http://localhost:3000` *(Login: `admin` / `admin`)*
- **Sample Target Microservice**: `http://localhost:8001/health`

### Option 2: Automated Local Setup Script

For local Python development without Docker:

```bash
# On Linux / macOS / WSL:
./scripts/setup.sh

# On Windows:
.\scripts\setup.bat
```

The script will automatically create `.venv`, install all dependencies, copy `.env.example`, execute database migrations, and seed initial services.

### Option 3: Manual Step-by-Step Setup

```bash
# 1. Create and activate Python 3.12 virtual environment
python -m venv .venv
source .venv/bin/activate  # Or: .\.venv\Scripts\activate on Windows

# 2. Install package in editable mode with development dependencies
pip install -e ".[dev]"

# 3. Copy environment configuration
cp .env.example .env

# 4. Run database migrations and seed data
alembic upgrade head
python scripts/seed_data.py

# 5. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

---

## 🧪 Sample Experiments Walkthrough

Chaos Probe includes pre-configured sample experiment definitions in `examples/sample_experiments/`:

### 1. Register the Target Microservice (if not seeded)
```bash
curl -X POST "http://localhost:8000/api/v1/services" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "payment-service",
       "base_url": "http://sample-target-service:8001",
       "health_check_url": "http://sample-target-service:8001/health",
       "container_id": "sample-target-service",
       "environment": "staging"
     }'
```

### 2. Inject Network Latency (250ms with Jitter)
```bash
curl -X POST "http://localhost:8000/api/v1/experiments" \
     -H "Content-Type: application/json" \
     -d @examples/sample_experiments/latency_experiment.json
```
*Response returns the generated `experiment_id`.*

### 3. Start the Experiment
```bash
curl -X POST "http://localhost:8000/api/v1/experiments/<EXPERIMENT_ID>/start"
```

### 4. Monitor Live Progress
```bash
curl -X GET "http://localhost:8000/api/v1/experiments/<EXPERIMENT_ID>/status"
```

### 5. View Interactive HTML Report
Open `http://localhost:8000/api/v1/experiments/<EXPERIMENT_ID>/report.html` in your web browser.

---

## 📡 Complete REST API Reference

All primary endpoints are served under `/api/v1`.

### 1. Services Management
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/services` | Register a new target service |
| `GET` | `/api/v1/services` | List all registered services |
| `GET` | `/api/v1/services/{id}` | Retrieve details of a registered service |
| `PUT` | `/api/v1/services/{id}` | Update service configuration or health check URL |
| `DELETE` | `/api/v1/services/{id}` | Deregister a service |
| `GET` | `/api/v1/services/{id}/health`| Perform an immediate active health probe |

### 2. Fault Strategies Catalog
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/faults` | List all 7 fault injection strategies with default profiles and parameter schemas |

### 3. Experiments Lifecycle
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/experiments` | Create and validate a chaos experiment |
| `GET` | `/api/v1/experiments` | List experiments (filter by `service_id` or `status`) |
| `GET` | `/api/v1/experiments/{id}` | Get experiment configuration and outcome |
| `GET` | `/api/v1/experiments/{id}/status`| Real-time lifecycle status and elapsed execution progress |
| `POST` | `/api/v1/experiments/{id}/start` | Trigger asynchronous execution of the experiment |
| `POST` | `/api/v1/experiments/{id}/abort` | Manually abort an active experiment with reason |

### 4. Reports & Analysis
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/experiments/{id}/report` | Retrieve synthesized JSON report and resilience score |
| `GET` | `/api/v1/experiments/{id}/report.html` | Render interactive HTML dashboard report |
| `GET` | `/api/v1/experiments/compare/{service_id}`| Historical resilience comparison across all runs |

### 5. Administration & Safety
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/admin/emergency-stop` | Emergency abort all active experiments and rollback all faults |
| `GET` | `/api/v1/admin/cleanups/unhealthy`| List failed rollbacks requiring operator intervention |
| `POST` | `/api/v1/admin/cleanups/{id}/retry`| Retry a failed rollback operation |

### 6. Observability
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/metrics` | Standard Prometheus metric scrape target |

---

## 🧪 Testing & Verification

Chaos Probe maintains a test suite covering unit logic, API integration, lifecycle state transitions, and real-world chaos scenarios:

```bash
# Run all tests
pytest tests/ -v

# Run only chaos verification scenarios
pytest tests/chaos/test_scenarios.py -v

# Run with test coverage analysis
pytest --cov=app --cov-report=term-missing
```

### Verified Test Suite Breakdown (35 Tests)
- `tests/unit/test_service_registry.py` (6 tests): Service validation, registration, duplicate checks, and health updates.
- `tests/unit/test_fault_strategies.py` (13 tests): Validation, execution, and rollback for all 7 fault strategies with mock container adapters.
- `tests/unit/test_monitoring.py` (1 test): Prometheus metrics registration and scrape emission.
- `tests/unit/test_analysis_and_reports.py` (3 tests): Resilience scoring mathematics, grade thresholds, and HTML report formatting.
- `tests/integration/test_service_api.py` (2 tests): Service API CRUD endpoints and error validation.
- `tests/integration/test_experiment_lifecycle.py` (4 tests): Full lifecycle execution, safety guardrail aborts, and concurrent lock protection.
- `tests/chaos/test_scenarios.py` (6 canonical scenarios):
  1. *Scenario 1: Network Latency (250ms injection & verification)*
  2. *Scenario 2: CPU Stress Injection*
  3. *Scenario 3: Memory Pressure with Guardrail Abort*
  4. *Scenario 4: Container Crash and Recovery Detection*
  5. *Scenario 5: Emergency Stop Manual Abort*
  6. *Scenario 6: Rollback Failure Handling and Operator Alerting*

---

## 📁 Project Directory Layout

```
Chaos-Probe/
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions CI lint, migrate & test workflow
├── app/
│   ├── api/
│   │   ├── dependencies.py            # DB session and service dependency providers
│   │   └── routes/
│   │       ├── admin.py               # Emergency stop & unhealthy rollback APIs
│   │       ├── experiments.py         # Experiment CRUD, status, and abort APIs
│   │       ├── faults.py              # Catalog of fault strategies
│   │       └── services.py            # Service registration & health check APIs
│   ├── analysis/
│   │   ├── recommendations.py         # Rule-based architectural remediation generator
│   │   ├── resilience_analyzer.py     # Metrics aggregator and outcome classifier
│   │   └── scoring.py                 # Deterministic 0-100 scoring model
│   ├── chaos/
│   │   ├── adapters/
│   │   │   ├── docker_adapter.py      # Docker SDK container adapter with mock fallback
│   │   │   └── network_adapter.py     # Linux tc netem traffic control adapter
│   │   ├── faults/
│   │   │   ├── container_kill.py      # Container termination & restart strategy
│   │   │   ├── cpu_stress.py          # CPU stress strategy
│   │   │   ├── memory_pressure.py     # Memory pressure strategy
│   │   │   ├── network_latency.py     # Network latency injection strategy
│   │   │   ├── packet_loss.py         # Packet loss injection strategy
│   │   │   ├── request_timeout.py     # Request timeout strategy
│   │   │   └── service_unavailable.py # 503 error injection strategy
│   │   ├── base.py                    # BaseFaultStrategy & FaultContext interface
│   │   ├── executor.py                # 10-state experiment execution engine
│   │   ├── registry.py                # Fault strategy registry
│   │   ├── rollback_manager.py        # Rollback tracking & error handler
│   │   └── safety_controller.py       # Concurrency locks & threshold guardrails
│   ├── core/
│   │   ├── config.py                  # Pydantic Settings configuration manager
│   │   ├── exceptions.py              # Domain-specific exceptions
│   │   ├── logging.py                 # Structured JSON & console logger
│   │   └── security.py                # Admin token header authentication
│   ├── database/
│   │   ├── base.py                    # SQLAlchemy 2.0 Base & TimestampMixin
│   │   ├── session.py                 # Engine and SessionLocal factory
│   │   └── models/
│   │       ├── experiment.py          # Experiment ORM entity
│   │       ├── metrics.py             # ExperimentMetric & ExperimentEvent ORM entities
│   │       ├── report.py              # ExperimentReport ORM entity
│   │       └── service.py             # Service ORM entity
│   ├── monitoring/
│   │   ├── health_checker.py          # Active HTTP probing service
│   │   └── prometheus.py              # Prometheus metrics registry & exporter
│   ├── reports/
│   │   ├── generator.py               # JSON & HTML report builder
│   │   └── templates/
│   │       └── report.html            # Standalone interactive HTML report template
│   ├── schemas/
│   │   ├── experiment.py              # Pydantic models for experiment requests/responses
│   │   ├── report.py                  # Pydantic models for reports and recommendations
│   │   └── service.py                 # Pydantic models for service registration/health
│   ├── services/
│   │   ├── experiment_manager.py      # Experiment lifecycle orchestration
│   │   └── service_registry.py        # Service registry domain logic
│   └── main.py                        # FastAPI application instance & lifespan setup
├── config/
│   ├── fault_profiles.yaml            # Pre-configured fault parameters
│   └── settings.yaml                  # Application default configuration
├── examples/
│   ├── sample_experiments/            # Ready-to-use JSON payloads for curl
│   │   ├── cpu_stress_experiment.json
│   │   ├── container_restart_experiment.json
│   │   ├── latency_experiment.json
│   │   ├── memory_pressure_experiment.json
│   │   ├── packet_loss_experiment.json
│   │   └── service_unavailable_experiment.json
│   └── sample_fastapi_service/        # Target microservice for chaos experiments
│       ├── Dockerfile
│       ├── main.py
│       └── requirements.txt
├── migrations/                        # Alembic database migration environment
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── monitoring/
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   └── chaos_probe_overview.json # Pre-built Grafana dashboard
│   │   └── provisioning/
│   │       ├── dashboards/
│   │       │   └── dashboard_provider.yml
│   │       └── datasources/
│   │           └── prometheus.yml
│   └── prometheus.yml                 # Prometheus scrape configuration
├── scripts/
│   ├── seed_data.py                   # Database seeder with sample services and reports
│   ├── setup.bat                      # Automated Windows setup script
│   └── setup.sh                       # Automated Linux/macOS setup script
├── tests/
│   ├── chaos/
│   │   └── test_scenarios.py          # 6 canonical chaos scenario verification tests
│   ├── integration/
│   │   ├── test_experiment_lifecycle.py
│   │   └── test_service_api.py
│   └── unit/
│       ├── test_analysis_and_reports.py
│       ├── test_fault_strategies.py
│       ├── test_monitoring.py
│       └── test_service_registry.py
├── .env.example                       # Template for environment variables
├── .gitignore                         # Git ignore specifications
├── alembic.ini                        # Alembic configuration
├── docker-compose.yml                 # Multi-container orchestration (DB, Redis, API, Target, Prometheus, Grafana)
├── Dockerfile                         # Container build specification for Chaos Probe API
├── PROGRESS.md                        # Phase completion checklist
├── pyproject.toml                     # Python package metadata & dependencies
└── README.md                          # Comprehensive project documentation
```

---

## 📄 License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.
