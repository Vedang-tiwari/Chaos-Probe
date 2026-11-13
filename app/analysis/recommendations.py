from typing import Any, Dict, List


def generate_recommendations(
    fault_type: str,
    outcome: str,
    availability_percentage: float,
    error_rate: float,
    baseline_latency_ms: float,
    injection_latency_ms: float,
    recovery_time_seconds: float | None,
) -> List[Dict[str, str]]:
    """Generates deterministic, actionable architectural recommendations based on experiment observations."""
    recs: List[Dict[str, str]] = []

    # 1. Latency & Timeout Recommendations
    if baseline_latency_ms > 0 and (injection_latency_ms / baseline_latency_ms) > 2.0:
        recs.append({
            "category": "Latency & Timeouts",
            "priority": "HIGH",
            "recommendation": f"Observed {injection_latency_ms:.1f}ms latency during injection vs {baseline_latency_ms:.1f}ms baseline. Implement aggressive downstream HTTP client timeouts (e.g. 500ms) with fallback degradation.",
        })
        recs.append({
            "category": "Circuit Breaking",
            "priority": "MEDIUM",
            "recommendation": "Configure circuit breakers to fast-fail calls when downstream latency degrades beyond acceptable SLA limits.",
        })

    # 2. Error Rate & Retry Recommendations
    if error_rate > 0.05:
        recs.append({
            "category": "Error Handling & Retries",
            "priority": "HIGH",
            "recommendation": f"Error rate reached {error_rate:.1%}. Implement exponential backoff retry policies with randomized jitter to prevent thundering herd problems.",
        })

    # 3. Availability & Redundancy Recommendations
    if availability_percentage < 95.0:
        recs.append({
            "category": "High Availability",
            "priority": "CRITICAL",
            "recommendation": f"Target service availability dropped to {availability_percentage:.1f}%. Deploy multiple container replicas across isolated availability zones behind a load balancer with active health probing.",
        })

    # 4. Recovery Performance Recommendations
    if recovery_time_seconds is None or recovery_time_seconds > 10.0:
        rec_dur_str = f"{recovery_time_seconds:.1f}s" if recovery_time_seconds is not None else "failed"
        recs.append({
            "category": "Self-Healing & Recovery",
            "priority": "HIGH",
            "recommendation": f"Service recovery took {rec_dur_str}. Optimize container restart policies, decrease probe intervals, and implement graceful connection draining.",
        })

    # 5. Fault-Specific Guidance
    if fault_type == "cpu_stress":
        recs.append({
            "category": "Resource Allocation",
            "priority": "MEDIUM",
            "recommendation": "Tune container CPU limits or introduce Horizontal Pod Autoscaling (HPA) based on CPU saturation thresholds.",
        })
    elif fault_type == "memory_pressure":
        recs.append({
            "category": "Memory Tuning",
            "priority": "MEDIUM",
            "recommendation": "Configure JVM/Node/Python memory bounds properly and monitor container cgroup memory limits to avoid OOMKills.",
        })

    if not recs:
        recs.append({
            "category": "Resilience Baseline",
            "priority": "LOW",
            "recommendation": "System demonstrated strong resilience under tested fault conditions. Maintain existing guardrails and schedule periodic regression experiments.",
        })

    return recs
