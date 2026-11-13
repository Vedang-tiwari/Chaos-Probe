import uuid
from datetime import datetime, timezone
import pytest
from app.analysis.recommendations import generate_recommendations
from app.analysis.resilience_analyzer import ResilienceAnalyzer
from app.analysis.scoring import calculate_resilience_score
from app.database.models.experiment import Experiment
from app.database.models.metrics import ExperimentMetric
from app.database.models.service import Service
from app.reports.generator import ReportGenerator


def test_calculate_resilience_score():
    # 1. Perfectly resilient system
    perfect = calculate_resilience_score(
        availability_percentage=100.0,
        error_rate=0.0,
        baseline_latency_ms=25.0,
        injection_latency_ms=28.0,  # ~1.12x degradation
        recovery_time_seconds=0.5,
    )
    assert perfect >= 98.0

    # 2. Severely degraded system
    degraded = calculate_resilience_score(
        availability_percentage=80.0,
        error_rate=0.15,
        baseline_latency_ms=25.0,
        injection_latency_ms=150.0,  # 6x degradation
        recovery_time_seconds=12.0,
    )
    assert 40.0 <= degraded <= 70.0

    # 3. Complete failure without recovery
    failed = calculate_resilience_score(
        availability_percentage=20.0,
        error_rate=0.80,
        baseline_latency_ms=25.0,
        injection_latency_ms=500.0,
        recovery_time_seconds=None,
    )
    assert failed < 25.0


def test_generate_recommendations():
    recs = generate_recommendations(
        fault_type="cpu_stress",
        outcome="DEGRADED",
        availability_percentage=90.0,
        error_rate=0.10,
        baseline_latency_ms=30.0,
        injection_latency_ms=120.0,  # 4x
        recovery_time_seconds=14.0,
    )
    categories = [r["category"] for r in recs]
    assert "Latency & Timeouts" in categories
    assert "Circuit Breaking" in categories
    assert "Error Handling & Retries" in categories
    assert "High Availability" in categories
    assert "Self-Healing & Recovery" in categories
    assert "Resource Allocation" in categories


def test_resilience_analyzer_and_report_generator(db_session, client):
    # 1. Create Service
    service = Service(
        name="billing-svc",
        base_url="http://billing:8000",
        health_check_url="http://billing:8000/health",
        status="HEALTHY",
    )
    db_session.add(service)
    db_session.commit()

    # 2. Create Experiment
    exp = Experiment(
        name="billing-latency-exp",
        service_id=service.id,
        fault_type="network_latency",
        configuration={"latency_ms": 500},
        status="COMPLETED",
        duration_seconds=30,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(exp)
    db_session.commit()

    # 3. Add sample metrics across baseline, injection, recovery
    # Baseline
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="latency_ms", metric_value=25.0, phase="baseline"))
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="availability", metric_value=1.0, phase="baseline"))
    # Injection
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="latency_ms", metric_value=220.0, phase="injection"))
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="availability", metric_value=1.0, phase="injection"))
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="error_rate", metric_value=0.02, phase="injection"))
    # Recovery
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="latency_ms", metric_value=28.0, phase="recovery"))
    db_session.add(ExperimentMetric(experiment_id=exp.id, metric_name="availability", metric_value=1.0, phase="recovery"))
    db_session.commit()

    # 4. Generate report
    generator = ReportGenerator(db=db_session)
    report = generator.generate_report(exp.id)

    assert report.outcome in ("DEGRADED", "SURVIVED")
    assert report.availability_percentage == 100.0
    assert report.average_latency == 220.0
    assert len(report.recommendations) > 0

    # 5. Render HTML
    html = generator.render_html(report)
    assert "<!DOCTYPE html>" in html
    assert "billing-latency-exp" in html
    assert "Resilience Score" in html
    assert "Engineering Recommendations" in html

    # 6. Test Report API Endpoints
    # JSON report
    json_res = client.get(f"/api/v1/experiments/{exp.id}/report")
    assert json_res.status_code == 200
    data = json_res.json()
    assert data["outcome"] == report.outcome
    assert data["availability_percentage"] == 100.0

    # HTML report
    html_res = client.get(f"/api/v1/experiments/{exp.id}/report.html")
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers["content-type"]
    assert "billing-latency-exp" in html_res.text

    # Compare API
    cmp_res = client.get(f"/api/v1/experiments/compare/{service.id}")
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.json()
    assert cmp_data["target_service_name"] == "billing-svc"
    assert cmp_data["total_experiments"] == 1
