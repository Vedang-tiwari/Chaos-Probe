from app.monitoring.prometheus import (
    EXPERIMENTS_TOTAL,
    MetricsTracker,
)


def test_metrics_tracker_and_prometheus_export(client):
    # Track metrics
    MetricsTracker.experiment_started()
    MetricsTracker.fault_applied("network_latency")
    MetricsTracker.record_probe("checkout-service", latency_seconds=0.35, is_healthy=True, phase="injection")
    MetricsTracker.record_recovery("checkout-service", recovery_seconds=4.2)
    MetricsTracker.fault_removed("network_latency")
    MetricsTracker.experiment_finished(status="COMPLETED", duration_seconds=30.0)

    # Scrape /metrics endpoint
    res = client.get("/metrics")
    assert res.status_code == 200
    text = res.text

    assert "chaos_probe_experiments_total" in text
    assert "chaos_probe_service_availability" in text
    assert "chaos_probe_request_latency_seconds" in text
    assert "chaos_probe_recovery_duration_seconds" in text
    assert "chaos_probe_active_faults" in text
