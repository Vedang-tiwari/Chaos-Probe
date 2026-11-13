"""Database seed script for Chaos Probe.

Registers default services and sample experiment data for initial bootstrapping.
Can be executed standalone:
    python scripts/seed_data.py
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.base import Base
from app.database.models.experiment import Experiment
from app.database.models.metrics import ExperimentMetric, ExperimentEvent
from app.database.models.report import ExperimentReport
from app.database.models.service import Service
from app.database.session import SessionLocal, engine

logger = get_logger("chaos_probe.scripts.seed_data")

# Known fixed UUIDs for deterministic references
SAMPLE_SERVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ORDER_SERVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
AUTH_SERVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")

SEED_SERVICES = [
    {
        "id": SAMPLE_SERVICE_ID,
        "name": "sample-target-service",
        "description": "Standard FastAPI sample microservice for chaos fault injection and resilience testing",
        "base_url": "http://sample-target-service:8001",
        "health_check_url": "http://sample-target-service:8001/health",
        "container_id": "sample-target-service",
        "environment": "development",
        "status": "HEALTHY",
    },
    {
        "id": ORDER_SERVICE_ID,
        "name": "order-processing-service",
        "description": "Core checkout and order dispatch backend pipeline",
        "base_url": "http://order-processing-service:8081",
        "health_check_url": "http://order-processing-service:8081/health",
        "container_id": "order-service",
        "environment": "staging",
        "status": "HEALTHY",
    },
    {
        "id": AUTH_SERVICE_ID,
        "name": "auth-gateway-service",
        "description": "OAuth2 authentication and session gateway service",
        "base_url": "http://auth-gateway-service:8082",
        "health_check_url": "http://auth-gateway-service:8082/health",
        "container_id": "auth-gateway",
        "environment": "staging",
        "status": "HEALTHY",
    },
]


def seed_database():
    """Seed services, sample experiments, and benchmark reports."""
    settings = get_settings()

    logger.info("Initializing schema tables if not present...")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        # 1. Seed Services
        registered_count = 0
        for svc_data in SEED_SERVICES:
            existing = session.execute(
                select(Service).where(Service.name == svc_data["name"])
            ).scalar_one_or_none()

            if not existing:
                service = Service(
                    id=svc_data["id"],
                    name=svc_data["name"],
                    description=svc_data["description"],
                    base_url=svc_data["base_url"],
                    health_check_url=svc_data["health_check_url"],
                    container_id=svc_data["container_id"],
                    environment=svc_data["environment"],
                    status=svc_data["status"],
                )
                session.add(service)
                registered_count += 1
                logger.info(f"Registered service: {svc_data['name']} (ID: {svc_data['id']})")
            else:
                logger.info(f"Service '{svc_data['name']}' already exists, skipping.")

        session.commit()
        logger.info(f"Services seeded successfully ({registered_count} new).")

        # 2. Seed a sample completed historical experiment & report for sample-target-service
        sample_exp_name = "baseline-network-latency-validation"
        existing_exp = session.execute(
            select(Experiment).where(Experiment.name == sample_exp_name)
        ).scalar_one_or_none()

        if not existing_exp:
            exp_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            started_at = now - timedelta(minutes=15)
            completed_at = now - timedelta(minutes=14)

            experiment = Experiment(
                id=exp_id,
                name=sample_exp_name,
                service_id=SAMPLE_SERVICE_ID,
                fault_type="network_latency",
                configuration={"latency_ms": 250, "jitter_ms": 25},
                status="COMPLETED",
                duration_seconds=30,
                started_at=started_at,
                completed_at=completed_at,
                created_at=started_at - timedelta(seconds=5),
            )
            session.add(experiment)

            # Add sample metrics
            for i in range(10):
                phase = "baseline" if i < 3 else ("injection" if i < 7 else "recovery")
                latency = 25.0 if phase == "baseline" else (275.0 if phase == "injection" else 30.0)

                metric = ExperimentMetric(
                    experiment_id=exp_id,
                    timestamp=started_at + timedelta(seconds=i * 3),
                    metric_name="latency_ms",
                    metric_value=latency,
                    phase=phase,
                )
                session.add(metric)

            # Add sample events
            events = [
                ("BASELINE_STARTED", "Starting baseline metrics observation", started_at),
                ("FAULT_INJECTED", "Injected network_latency of 250ms with jitter 25ms", started_at + timedelta(seconds=10)),
                ("RECOVERY_STARTED", "Fault removed. Observing service recovery", started_at + timedelta(seconds=20)),
                ("EXPERIMENT_COMPLETED", "Experiment execution completed normally", completed_at),
            ]
            for ev_type, desc, ts in events:
                event = ExperimentEvent(
                    experiment_id=exp_id,
                    event_type=ev_type,
                    message=desc,
                    timestamp=ts,
                    event_metadata={"phase": ev_type},
                )
                session.add(event)

            # Add benchmark Report with resilience score
            report = ExperimentReport(
                experiment_id=exp_id,
                outcome="DEGRADED",
                availability_percentage=100.0,
                average_latency=125.0,
                maximum_latency=282.4,
                error_rate=0.0,
                recovery_time_seconds=2.1,
                summary={
                    "resilience_score": 85.5,
                    "target_service_name": "sample-target-service",
                    "fault_type": "network_latency",
                    "total_samples": 10,
                    "baseline_latency_ms": 25.0,
                    "fault_latency_ms": 275.0,
                    "recovery_latency_ms": 30.0,
                    "latency_degradation_pct": 1000.0,
                },
                recommendations=[
                    {
                        "priority": "MEDIUM",
                        "title": "Configure Adaptive Client Request Timeouts",
                        "description": "Observed mean latency increased to 275ms during injected latency. Configure client timeouts to 500ms with circuit breaker tripping after 5 consecutive failures.",
                        "category": "TIMEOUT_AND_RETRY",
                    },
                    {
                        "priority": "LOW",
                        "title": "Establish Baseline Latency SLO Alerting",
                        "description": "Service returned 200 OK throughout the experiment, demonstrating good fallback stability without cascading crashes.",
                        "category": "MONITORING",
                    },
                ],
                generated_at=completed_at,
            )
            session.add(report)

            session.commit()
            logger.info(f"Sample completed experiment '{sample_exp_name}' and report seeded (ID: {exp_id}).")
        else:
            logger.info("Sample experiment already seeded.")

    logger.info("Database seeding process completed.")


if __name__ == "__main__":
    try:
        seed_database()
        print("\nSeed data loaded successfully!")
    except Exception as exc:
        logger.error(f"Failed to seed database: {exc}", exc_info=True)
        sys.exit(1)
