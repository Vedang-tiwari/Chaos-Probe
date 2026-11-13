from typing import Dict


def calculate_resilience_score(
    availability_percentage: float,
    error_rate: float,
    baseline_latency_ms: float,
    injection_latency_ms: float,
    recovery_time_seconds: float | None,
    max_recovery_window_seconds: float = 30.0,
    weights: Dict[str, float] | None = None,
) -> float:
    """Calculates a deterministic 0-100 system resilience score based on normalized metrics."""
    if weights is None:
        weights = {
            "availability": 0.35,
            "error_rate": 0.25,
            "latency": 0.20,
            "recovery": 0.20,
        }

    # 1. Availability component (0 to 100)
    avail_score = max(0.0, min(100.0, availability_percentage))

    # 2. Error rate component (0 to 100)
    # 0% error rate = 100, 100% error rate = 0
    err_score = max(0.0, min(100.0, (1.0 - error_rate) * 100.0))

    # 3. Latency degradation component (0 to 100)
    if baseline_latency_ms > 0:
        ratio = injection_latency_ms / baseline_latency_ms
    else:
        ratio = 1.0

    if ratio <= 1.2:
        lat_score = 100.0
    elif ratio >= 5.0:
        lat_score = 0.0
    else:
        # Linear degradation between 1.2x and 5.0x
        lat_score = max(0.0, 100.0 - ((ratio - 1.2) / (5.0 - 1.2)) * 100.0)

    # 4. Recovery performance component (0 to 100)
    if recovery_time_seconds is None:
        rec_score = 0.0
    elif recovery_time_seconds <= 1.0:
        rec_score = 100.0
    elif recovery_time_seconds >= max_recovery_window_seconds:
        rec_score = 10.0
    else:
        rec_score = max(
            10.0,
            100.0 - ((recovery_time_seconds - 1.0) / (max_recovery_window_seconds - 1.0)) * 90.0,
        )

    # Weighted composite score
    total = (
        avail_score * weights["availability"]
        + err_score * weights["error_rate"]
        + lat_score * weights["latency"]
        + rec_score * weights["recovery"]
    )

    return round(max(0.0, min(100.0, total)), 1)

