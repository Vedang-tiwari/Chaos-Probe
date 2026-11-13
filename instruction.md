# CHAOS PROBE
## AI Coding Agent — Project Implementation Instructions

---

# 1. PROJECT OVERVIEW

## Project Name
Chaos Probe

## Project Type
Chaos Engineering / Fault Injection / Distributed Systems Resilience Testing Platform.

## Core Concept

Chaos Probe is a controlled fault-injection platform that tests the resilience and reliability of running applications and microservices.

It deliberately introduces failures into a target application to understand how the system behaves under unexpected conditions.

The platform observes the target service before, during, and after fault injection.

It collects metrics, identifies failures, measures recovery time, and generates comprehensive experiment reports.

### Core Mission

Answer the following questions:

- What happens when a service becomes unavailable?
- Does the application survive network latency?
- Does it recover when CPU or memory resources become constrained?
- What happens when a dependent service crashes?
- Does the application recover automatically?
- How long does recovery take?
- Does the service experience cascading failures?
- Which components become bottlenecks?
- Does the system meet its reliability expectations?

**The final output should tell developers what survived, what failed, how long recovery took, and why.**

---

# 2. PROBLEM STATEMENT

Modern distributed applications consist of multiple services, APIs, databases, queues, and external dependencies.

A service might work perfectly under normal conditions but fail unexpectedly when:

- A database becomes unavailable.
- An API dependency becomes slow.
- Network connectivity is interrupted.
- CPU utilization increases.
- Memory becomes constrained.
- A container unexpectedly stops.
- Requests start timing out.
- Multiple dependencies fail simultaneously.

Traditional testing primarily verifies expected application behaviour.

It does not necessarily establish whether the application can survive infrastructure failures.

Chaos Probe addresses this problem by providing a controlled environment to simulate infrastructure and application failures.

---

# 3. PROJECT OBJECTIVES

Build a platform that can:

1. Register and manage target services.
2. Monitor the health of running services.
3. Execute controlled fault-injection experiments.
4. Support multiple fault types.
5. Collect application and infrastructure metrics.
6. Detect service degradation.
7. Measure failure and recovery duration.
8. Automatically stop experiments when safety thresholds are exceeded.
9. Restore the system after experiments.
10. Generate detailed experiment reports.
11. Maintain experiment history.
12. Compare service resilience across multiple experiments.

---

# 4. TECHNOLOGY STACK

Use the following technology stack.

## Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL

## Fault Injection Engine

- Python
- Docker SDK for Python
- Docker Engine API
- Linux networking utilities where applicable
- Controlled resource constraints

## Background Processing

- Celery
- Redis

## Monitoring and Observability

- Prometheus
- Grafana
- OpenTelemetry
- Prometheus Python Client

## Containerization

- Docker
- Docker Compose

## Testing

- Pytest
- HTTPX
- Testcontainers (optional)
- Mock fault-injection adapters

## Development Tools

- Git
- GitHub Actions
- Ruff
- MyPy
- Pre-commit

### Important

Do not introduce Kubernetes, Terraform, or complex distributed orchestration in the initial implementation.

Keep the first version Docker-based.

Design the architecture so Kubernetes support can be introduced later.

---

# 5. HIGH-LEVEL ARCHITECTURE

The platform should contain the following major components.

## 5.1 API Gateway / Backend

Responsible for:

- Exposing REST APIs.
- Registering target services.
- Managing experiments.
- Validating experiment configurations.
- Returning experiment results.
- Managing experiment history.

Technology: FastAPI.

## 5.2 Service Registry

Maintains information about monitored applications.

Each registered service should contain:

- Service ID
- Service name
- Description
- Base URL
- Health-check endpoint
- Container ID (when applicable)
- Environment
- Service status
- Registration timestamp

Support Docker container targets initially.

## 5.3 Chaos Engine

This is the primary component of Chaos Probe.

It executes controlled fault-injection operations.

Responsibilities:

- Validate experiment configurations.
- Check target availability.
- Execute fault injections.
- Track experiment duration.
- Monitor fault status.
- Stop experiments.
- Trigger cleanup and recovery.
- Record experiment events.

Implement fault injection through separate strategy classes.

Do not place every fault implementation inside one large Python file.

## 5.4 Experiment Scheduler

Responsible for executing experiments asynchronously.

Responsibilities:

- Queue experiment execution.
- Manage experiment lifecycle.
- Track execution progress.
- Prevent conflicting experiments on the same target.
- Support cancellation.
- Enforce experiment timeouts.

Use Celery and Redis.

## 5.5 Monitoring Engine

Collects metrics before, during, and after experiments.

Metrics include:

- CPU utilization
- Memory utilization
- Request latency
- Request throughput
- HTTP error rate
- Service availability
- Container restart count
- Recovery time

Use Prometheus for metrics collection.

Use OpenTelemetry for traces and instrumentation.

## 5.6 Analysis Engine

Analyzes experiment results.

It should determine:

- Whether the service survived.
- Whether the service became degraded.
- Whether the service became unavailable.
- Whether recovery was successful.
- How long recovery took.
- Whether the experiment triggered unexpected failures.

Start with deterministic rule-based analysis.

Do not introduce an LLM just to label experiment outcomes.

## 5.7 Reporting Engine

Generates structured experiment reports.

Reports should contain:

- Experiment summary
- Target service
- Fault type
- Fault configuration
- Experiment duration
- Initial health status
- Final health status
- Maximum observed latency
- Error rate
- Availability percentage
- Recovery duration
- Experiment outcome
- Detected anomalies
- Recommendations

Support JSON reports initially.

Add downloadable HTML reports later.

---

# 6. FAULT INJECTION MODULES

Implement the following fault types.

Each fault must have its own independent implementation.

## 6.1 Network Latency Injection

Simulates slow network communication.

Example:

Introduce 500ms latency to a target container.

Configurable parameters:

- Latency in milliseconds
- Jitter
- Duration
- Optional packet correlation

Expected observations:

- Increased request latency.
- Increased timeout frequency.
- Potential throughput degradation.

Implementation:

Use Linux traffic control (`tc netem`) in an isolated Linux environment.

Do not execute arbitrary host networking commands.

Use an isolated Docker network and controlled execution adapters.

## 6.2 Network Packet Loss

Simulates unreliable network communication.

Parameters:

- Packet loss percentage
- Duration
- Target interface

Example:

Inject 10% packet loss for 30 seconds.

Observe:

- Failed requests.
- Increased latency.
- Retry behaviour.
- Service availability.

## 6.3 CPU Stress

Simulates CPU resource exhaustion.

Parameters:

- CPU utilization target
- Number of worker processes
- Duration

Observe:

- CPU utilization.
- Request latency.
- Throughput.
- Health-check failures.

Prefer Docker CPU quotas or controlled stress workers.

## 6.4 Memory Pressure

Simulates memory constraints.

Parameters:

- Memory allocation limit
- Duration
- Maximum allowed allocation

Observe:

- Memory utilization.
- Container restarts.
- Out-of-memory events.
- Service degradation.

Never allow the experiment to exhaust the host machine's memory.

## 6.5 Container Termination

Simulates unexpected container failure.

Parameters:

- Target container
- Termination method
- Recovery strategy

Observe:

- Service downtime.
- Restart behaviour.
- Health-check recovery.
- Recovery duration.

Initially support only dedicated test containers.

Do not terminate arbitrary production containers.

## 6.6 Service Unavailability

Simulates a dependency becoming unavailable.

Examples:

- Database unavailable.
- Redis unavailable.
- External API unavailable.

Implement this through isolated dependency containers or controllable network policies.

Observe:

- Application error rate.
- Retry behaviour.
- Circuit breaker behaviour.
- Graceful degradation.

## 6.7 Request Timeout Injection

Simulates slow dependency responses.

Parameters:

- Additional delay
- Duration
- Target dependency

Observe:

- Request timeout frequency.
- Retry behaviour.
- Application response latency.

---

# 7. EXPERIMENT LIFECYCLE

Every experiment must follow a strict lifecycle.

Implement these states:

1. CREATED
2. VALIDATING
3. BASELINE_COLLECTION
4. RUNNING
5. FAULT_INJECTED
6. OBSERVING
7. RECOVERING
8. COMPLETED
9. FAILED
10. ABORTED

## Execution Workflow

### Step 1: Create Experiment

The user selects:

- Target service
- Fault type
- Fault parameters
- Experiment duration
- Safety thresholds

### Step 2: Validation

Verify:

- Target exists.
- Target is running.
- Target is healthy.
- Fault parameters are valid.
- Experiment duration is within allowed limits.
- Target is authorized for testing.
- No conflicting experiment is running.

### Step 3: Baseline Collection

Collect metrics before injecting faults.

Baseline duration should be configurable.

Default: 30 seconds.

### Step 4: Fault Injection

Execute the selected fault strategy.

Record:

- Injection start time.
- Fault configuration.
- Target service.
- Execution result.

### Step 5: Observation

Continuously collect metrics.

Detect:

- Service downtime.
- Increased latency.
- HTTP errors.
- Resource exhaustion.
- Container restarts.

### Step 6: Recovery

Remove the injected fault.

Restore previous configurations.

Verify that the target service returns to a healthy state.

### Step 7: Analysis

Compare baseline, fault-injection, and recovery metrics.

Determine the final experiment outcome.

### Step 8: Report Generation

Save the complete experiment report.

---

# 8. EXPERIMENT SAFETY SYSTEM

This is one of the most important parts of Chaos Probe.

Never implement unrestricted fault injection.

Implement a safety controller.

## Mandatory Safety Features

### A. Maximum Experiment Duration

Default maximum duration: 120 seconds.

Allow configuration within an administrator-defined limit.

### B. Automatic Rollback

Every fault implementation must have:

- apply()
- verify()
- rollback()
- cleanup()

Rollback must execute even when an experiment fails unexpectedly.

Use Python context managers or equivalent lifecycle management where appropriate.

### C. Emergency Stop

Provide an emergency-stop API.

When activated:

- Stop active fault injection.
- Cancel pending experiments.
- Trigger rollback.
- Record the abort reason.
- Verify recovery where possible.

### D. Resource Limits

Set maximum CPU and memory limits for stress workers.

Never allow resource consumption to exceed configured limits.

### E. Target Isolation

Initially support only explicitly registered test services.

Require explicit authorization for every target.

### F. Concurrent Experiment Protection

Prevent conflicting experiments from executing simultaneously against the same service.

### G. Safety Thresholds

Allow users to configure:

- Maximum error rate.
- Maximum latency.
- Minimum availability.
- Maximum CPU utilization.
- Maximum memory utilization.

Automatically abort an experiment when a critical threshold is crossed.

### H. Cleanup Verification

Do not mark an experiment as successfully completed if rollback fails.

Record rollback failures separately.

Expose an unhealthy cleanup state requiring operator attention.

---

# 9. DATABASE DESIGN

Use PostgreSQL.

Create the following tables.

## services

Fields:

- id: UUID
- name: String
- description: Text
- base_url: String
- health_check_url: String
- container_id: String
- environment: String
- status: String
- created_at: Timestamp
- updated_at: Timestamp

## experiments

Fields:

- id: UUID
- name: String
- service_id: UUID
- fault_type: String
- configuration: JSONB
- status: String
- duration_seconds: Integer
- started_at: Timestamp
- completed_at: Timestamp
- created_at: Timestamp
- abort_reason: Text

## experiment_metrics

Fields:

- id: UUID
- experiment_id: UUID
- metric_name: String
- metric_value: Float
- timestamp: Timestamp
- phase: String

The phase should identify:

- baseline
- injection
- observation
- recovery

## experiment_events

Fields:

- id: UUID
- experiment_id: UUID
- event_type: String
- message: Text
- metadata: JSONB
- timestamp: Timestamp

## experiment_reports

Fields:

- id: UUID
- experiment_id: UUID
- outcome: String
- availability_percentage: Float
- average_latency: Float
- maximum_latency: Float
- error_rate: Float
- recovery_time_seconds: Float
- summary: JSONB
- recommendations: JSONB
- generated_at: Timestamp

Use Alembic migrations.

Create appropriate foreign keys, indexes, and constraints.

---

# 10. API DESIGN

Use REST APIs.

Base URL:

/api/v1

## Service APIs

POST /services

Register a service.

GET /services

List registered services.

GET /services/{service_id}

Retrieve service details.

DELETE /services/{service_id}

Remove a registered service.

GET /services/{service_id}/health

Check service health.

## Experiment APIs

POST /experiments

Create an experiment.

GET /experiments

List experiments.

GET /experiments/{experiment_id}

Retrieve experiment details.

POST /experiments/{experiment_id}/start

Start an experiment.

POST /experiments/{experiment_id}/abort

Abort an experiment.

GET /experiments/{experiment_id}/status

Get execution status.

GET /experiments/{experiment_id}/metrics

Retrieve experiment metrics.

GET /experiments/{experiment_id}/report

Retrieve experiment report.

## Fault APIs

GET /faults

List available fault types.

GET /faults/{fault_type}

Retrieve fault documentation and supported configuration.

## Emergency API

POST /admin/emergency-stop

Trigger emergency shutdown and cleanup.

Protect administrative endpoints with authentication and authorization.

---

# 11. ANALYSIS AND RESILIENCE SCORING

Build a deterministic analysis engine.

Do not make the scoring system dependent on subjective AI-generated assessments.

## Experiment Outcomes

Classify each experiment into:

### SURVIVED

The service remained operational and satisfied configured reliability thresholds.

### DEGRADED

The service continued operating but experienced significant performance degradation.

### FAILED

The service became unavailable or violated critical reliability thresholds.

### RECOVERED

The service experienced a failure but successfully returned to a healthy state.

### RECOVERY_FAILED

The service did not recover within the configured recovery window.

### ABORTED

The experiment was stopped by the safety controller or operator.

Store the primary outcome and additional recovery information separately.

## Resilience Score

Implement an initial score between 0 and 100.

Suggested weighted components:

- Availability: 35%
- Error rate: 25%
- Latency degradation: 20%
- Recovery performance: 20%

Normalize every component before calculating the score.

Use configurable thresholds.

Document the scoring methodology.

Important: A score is a comparative engineering indicator, not a universally accepted measure of system resilience.

---

# 12. MONITORING AND OBSERVABILITY

Expose Prometheus metrics.

Suggested metrics:

chaos_probe_experiments_total

chaos_probe_experiments_running

chaos_probe_fault_injections_total

chaos_probe_experiment_duration_seconds

chaos_probe_service_availability

chaos_probe_request_latency_seconds

chaos_probe_request_errors_total

chaos_probe_recovery_duration_seconds

chaos_probe_active_faults

chaos_probe_rollback_failures_total

Create Grafana dashboards showing:

1. Experiment Overview
2. Service Health
3. Fault Injection Timeline
4. CPU and Memory Utilization
5. Request Latency
6. Error Rate
7. Recovery Behaviour
8. Experiment History

Use OpenTelemetry instrumentation to capture backend execution traces.

---

# 13. PROJECT DIRECTORY STRUCTURE

Follow this structure.

chaos-probe/

├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── services.py
│   │   │   ├── experiments.py
│   │   │   ├── faults.py
│   │   │   ├── metrics.py
│   │   │   └── admin.py
│   │   └── dependencies.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── database/
│   │   ├── session.py
│   │   ├── base.py
│   │   └── models/
│   │       ├── service.py
│   │       ├── experiment.py
│   │       ├── metrics.py
│   │       └── report.py
│   │
│   ├── schemas/
│   │   ├── service.py
│   │   ├── experiment.py
│   │   ├── fault.py
│   │   └── report.py
│   │
│   ├── services/
│   │   ├── service_registry.py
│   │   ├── experiment_manager.py
│   │   ├── monitoring_service.py
│   │   ├── analysis_service.py
│   │   └── report_service.py
│   │
│   ├── chaos/
│   │   ├── engine.py
│   │   ├── base.py
│   │   ├── executor.py
│   │   ├── safety_controller.py
│   │   ├── rollback_manager.py
│   │   │
│   │   ├── faults/
│   │   │   ├── network_latency.py
│   │   │   ├── packet_loss.py
│   │   │   ├── cpu_stress.py
│   │   │   ├── memory_pressure.py
│   │   │   ├── container_kill.py
│   │   │   ├── service_unavailable.py
│   │   │   └── request_timeout.py
│   │   │
│   │   └── adapters/
│   │       ├── docker_adapter.py
│   │       └── network_adapter.py
│   │
│   ├── monitoring/
│   │   ├── prometheus.py
│   │   ├── collectors.py
│   │   ├── health_checker.py
│   │   └── telemetry.py
│   │
│   ├── analysis/
│   │   ├── resilience_analyzer.py
│   │   ├── scoring.py
│   │   └── recommendations.py
│   │
│   ├── reports/
│   │   ├── generator.py
│   │   └── templates/
│   │
│   └── workers/
│       ├── celery_app.py
│       └── experiment_tasks.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── chaos/
│   └── fixtures/
│
├── config/
│   ├── settings.yaml
│   └── fault_profiles.yaml
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│
├── examples/
│   ├── sample_fastapi_service/
│   └── sample_experiments/
│
├── scripts/
│   ├── setup.sh
│   └── seed_data.py
│
├── migrations/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── INSTRUCTION.md

The agent may adjust the structure when technically justified, but must preserve clear separation between API, fault execution, monitoring, analysis, and reporting.

---

# 14. IMPLEMENTATION PHASES

Implement the project incrementally.

Do not generate the entire project in one step.

## PHASE 1 — Foundation

Tasks:

- Initialize Python project.
- Configure FastAPI.
- Configure PostgreSQL.
- Configure SQLAlchemy.
- Set up Alembic.
- Configure Pydantic settings.
- Implement structured logging.
- Create Docker Compose.
- Implement service registration.
- Implement service health checking.

Deliverable:

A working backend that can register and monitor target services.

## PHASE 2 — Fault Injection Engine

Tasks:

- Create the base fault interface.
- Implement fault registry.
- Implement Docker adapter.
- Implement network latency.
- Implement packet loss.
- Implement CPU stress.
- Implement memory pressure.
- Implement controlled container termination.
- Implement fault rollback.

Deliverable:

A functioning fault-injection engine.

## PHASE 3 — Experiment Management

Tasks:

- Implement experiment creation.
- Implement experiment lifecycle.
- Implement background workers.
- Implement experiment scheduling.
- Implement cancellation.
- Implement experiment locking.
- Implement safety controller.
- Implement emergency stop.

Deliverable:

Ability to execute controlled experiments asynchronously.

## PHASE 4 — Monitoring

Tasks:

- Integrate Prometheus.
- Collect CPU metrics.
- Collect memory metrics.
- Collect request latency.
- Collect HTTP error rates.
- Implement baseline collection.
- Implement recovery monitoring.
- Add OpenTelemetry instrumentation.

Deliverable:

A monitoring system that captures application behaviour throughout experiments.

## PHASE 5 — Analysis Engine

Tasks:

- Compare baseline and injection metrics.
- Calculate availability.
- Calculate latency degradation.
- Calculate error rate.
- Measure recovery time.
- Classify experiment outcomes.
- Generate resilience scores.
- Generate recommendations.

Deliverable:

An automated experiment analysis engine.

## PHASE 6 — Reporting

Tasks:

- Generate JSON reports.
- Generate HTML reports.
- Store experiment history.
- Add experiment comparison.
- Implement report retrieval APIs.

Deliverable:

Comprehensive experiment reports.

## PHASE 7 — Testing and Reliability

Tasks:

- Write unit tests.
- Write integration tests.
- Test every fault strategy.
- Test rollback behaviour.
- Test emergency stop.
- Test failed experiments.
- Test concurrent experiment protection.
- Test resource limits.
- Test database persistence.
- Test complete experiment lifecycle.

Deliverable:

A reliable and testable chaos engineering platform.

## PHASE 8 — Observability and Deployment

Tasks:

- Configure Prometheus.
- Configure Grafana.
- Create dashboards.
- Configure Docker Compose deployment.
- Add GitHub Actions.
- Add linting.
- Add type checking.
- Add automated tests.
- Document setup and deployment.

Deliverable:

A production-style local deployment.

---

# 15. TESTING REQUIREMENTS

Testing is mandatory.

Implement the following scenarios.

### Scenario 1: Network Latency

Inject 500ms network latency.

Verify:

- Latency increases.
- Metrics are recorded.
- Fault is removed.
- Service recovers.

### Scenario 2: CPU Stress

Inject controlled CPU pressure.

Verify:

- CPU utilization increases.
- Application performance is measured.
- CPU stress is stopped.
- Resource utilization returns toward baseline.

### Scenario 3: Memory Pressure

Introduce controlled memory pressure.

Verify:

- Memory utilization increases.
- Safety thresholds work.
- Memory workers terminate.
- No host-level resource exhaustion occurs.

### Scenario 4: Container Failure

Terminate a dedicated test container.

Verify:

- Service becomes unavailable.
- Failure is detected.
- Recovery is measured.
- The final outcome is classified correctly.

### Scenario 5: Emergency Stop

Start an experiment and trigger emergency stop.

Verify:

- Fault injection stops.
- Rollback executes.
- Experiment becomes ABORTED.
- Cleanup status is recorded.

### Scenario 6: Rollback Failure

Simulate an adapter cleanup failure.

Verify:

- The failure is recorded.
- The experiment is not marked as successfully recovered.
- The system exposes the cleanup issue.
- An operator can identify the affected target.

---

# 16. DEVELOPMENT STANDARDS

The coding agent MUST follow these rules.

## Code Quality

- Follow PEP 8.
- Use type hints.
- Use descriptive function and class names.
- Use Pydantic for request validation.
- Use dependency injection.
- Avoid unnecessary abstractions.
- Keep functions focused.
- Use structured logging.
- Handle exceptions explicitly.

## Architecture

- Use modular architecture.
- Keep fault implementations independent.
- Use strategy pattern for fault injection.
- Use adapters for infrastructure interactions.
- Separate orchestration from execution.
- Separate monitoring from analysis.
- Keep database operations outside business logic where practical.

## Reliability

- Every fault must support rollback.
- Every experiment must have a timeout.
- Every experiment must have a unique ID.
- Every execution must be auditable.
- Never silently ignore execution failures.
- Never assume rollback succeeded.
- Make cleanup idempotent.
- Handle worker crashes and interrupted tasks.

## Security

- Never execute arbitrary shell commands supplied by API users.
- Never accept unrestricted container IDs.
- Validate targets against the service registry.
- Restrict Docker socket access.
- Do not expose Docker administrative operations through public APIs.
- Keep secrets in environment variables.
- Protect administrative endpoints.
- Use least-privilege execution wherever possible.

## Testing

- Maintain meaningful test coverage.
- Mock external infrastructure in unit tests.
- Use isolated Docker environments for integration tests.
- Never run destructive chaos tests against production infrastructure.

---

# 17. INITIAL MVP SCOPE

Do not attempt to implement everything immediately.

The first working version must support:

1. Registering Docker-based target services.
2. Checking service health.
3. Creating experiments.
4. Injecting network latency.
5. Injecting CPU pressure.
6. Injecting memory pressure.
7. Collecting baseline metrics.
8. Collecting fault-injection metrics.
9. Automatic rollback.
10. Emergency stop.
11. Calculating recovery time.
12. Generating JSON experiment reports.

After the MVP works reliably, add:

- Packet loss.
- Container termination.
- Dependency failure.
- Advanced resilience scoring.
- Experiment comparison.
- Grafana dashboards.
- HTML reports.
- Kubernetes support.

Do not sacrifice reliability for the number of supported fault types.

---

# 18. EXPECTED FINAL PRODUCT

The completed Chaos Probe platform should allow a developer to:

1. Start their application using Docker.
2. Register the application in Chaos Probe.
3. Select an experiment.
4. Configure fault parameters.
5. Execute the experiment.
6. Observe live metrics.
7. Watch the application respond to the injected failure.
8. Automatically restore the environment.
9. View the experiment report.
10. Compare results across multiple experiments.

### Example Experiment

Target:

payment-service

Fault:

Network Latency

Configuration:

- Latency: 500ms
- Jitter: 100ms
- Duration: 30 seconds

Example result:

Experiment ID: CP-EXP-001

Target: payment-service

Fault: Network Latency

Status: COMPLETED

Results:

- Baseline latency: 45ms
- Maximum observed latency: 620ms
- Baseline error rate: 0.2%
- Maximum error rate: 4.5%
- Availability: 98.7%
- Recovery time: 8.4 seconds

Outcome: DEGRADED

Recovery: SUCCESSFUL

Recommendations:

- Introduce appropriate request timeouts.
- Implement retry policies with exponential backoff.
- Consider circuit breakers for downstream dependencies.
- Review latency budgets for payment operations.

These are illustrative results, not hardcoded outputs. All reported values must come from actual experiment measurements.

---

# 19. DEFINITION OF DONE

Chaos Probe is considered complete when:

- Services can be registered and monitored.
- Experiments can be created and executed.
- Multiple fault types work.
- Fault injection is isolated and controlled.
- Metrics are collected continuously.
- Experiments can be aborted.
- Rollback works reliably.
- Recovery is measured.
- Reports are generated from actual observations.
- Experiment history is persisted.
- Automated tests pass.
- Docker Compose deployment works.
- Documentation explains installation, configuration, architecture, and usage.

---

# 20. INSTRUCTIONS TO THE AI CODING AGENT

You are acting as a Senior Backend Engineer, Distributed Systems Engineer, and Chaos Engineering specialist.

Your responsibility is to build Chaos Probe as a maintainable, reliable, modular engineering platform.

Follow these instructions:

1. Read this entire INSTRUCTION.md before writing code.
2. Understand the architecture and implementation phases.
3. Inspect the existing repository before creating or modifying files.
4. Do not overwrite existing working code without understanding it.
5. Start with Phase 1.
6. Implement one phase at a time.
7. Explain the implementation briefly before making major architectural decisions.
8. Create functional code, not placeholder implementations.
9. Do not leave core functionality as TODO comments.
10. Write tests alongside implementation.
11. Verify imports and dependencies.
12. Run tests after completing each phase.
13. Fix errors before proceeding.
14. Update README.md whenever a major feature is implemented.
15. Maintain an implementation progress checklist.
16. Keep configuration externalized.
17. Never hardcode credentials.
18. Never execute uncontrolled destructive operations.
19. Prioritize fault isolation, automatic cleanup, and system safety.
20. Do not claim that an experiment succeeded unless its execution and cleanup were verified.

### Agent Workflow

For every phase:

1. Explain the objective.
2. Identify files to create or modify.
3. Implement the functionality.
4. Write relevant tests.
5. Execute tests.
6. Fix discovered issues.
7. Update documentation.
8. Mark completed tasks in the progress checklist.
9. Move to the next phase only after the current phase is verified.

### Final Engineering Principle

Chaos Probe must not merely inject failures.

It must measure how a system behaves under failure, determine whether it survives, establish whether it recovers, and provide evidence explaining the result.

**Build an actual chaos engineering platform, not a collection of Python scripts that randomly kill Docker containers.**