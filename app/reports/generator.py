from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.analysis.resilience_analyzer import ResilienceAnalyzer
from app.database.models.experiment import Experiment
from app.database.models.report import ExperimentReport
from app.database.models.service import Service

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


class ReportGenerator:
    """Generates structured JSON reports and interactive HTML dashboards."""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = ResilienceAnalyzer(db=db)
        self.template_dir = Path(__file__).parent / "templates"
        if HAS_JINJA2:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=True,
            )
        else:
            self.jinja_env = None

    def generate_report(self, experiment_id: uuid.UUID) -> ExperimentReport:
        """Analyzes experiment results and persists an ExperimentReport entity."""
        analysis = self.analyzer.analyze_experiment(experiment_id)

        # Check if report already exists for this experiment
        stmt = select(ExperimentReport).where(ExperimentReport.experiment_id == experiment_id)
        report = self.db.scalars(stmt).first()

        if not report:
            report = ExperimentReport(
                experiment_id=experiment_id,
                outcome=analysis.outcome,
                availability_percentage=analysis.availability_percentage,
                average_latency=analysis.average_latency_ms,
                maximum_latency=analysis.maximum_latency_ms,
                error_rate=analysis.error_rate,
                recovery_time_seconds=analysis.recovery_time_seconds,
                summary=analysis.summary,
                recommendations=analysis.recommendations,
                generated_at=datetime.now(timezone.utc),
            )
            self.db.add(report)
        else:
            report.outcome = analysis.outcome
            report.availability_percentage = analysis.availability_percentage
            report.average_latency = analysis.average_latency_ms
            report.maximum_latency = analysis.maximum_latency_ms
            report.error_rate = analysis.error_rate
            report.recovery_time_seconds = analysis.recovery_time_seconds
            report.summary = analysis.summary
            report.recommendations = analysis.recommendations
            report.generated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(report)
        return report

    def render_html(self, report: ExperimentReport) -> str:
        """Renders report into interactive HTML document."""
        summary = report.summary or {}
        context = {
            "summary": summary,
            "outcome": report.outcome,
            "resilience_score": summary.get("resilience_score", 0.0),
            "availability_percentage": round(report.availability_percentage, 1),
            "baseline_latency_ms": round(summary.get("baseline_latency_ms", 0.0), 1),
            "maximum_latency_ms": round(report.maximum_latency, 1),
            "recovery_time_seconds": report.recovery_time_seconds,
            "recommendations": report.recommendations or [],
            "generated_at": report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        if self.jinja_env is not None:
            template = self.jinja_env.get_template("report.html")
            return template.render(**context)

        # Built-in fallback renderer when jinja2 is not installed
        template_file = self.template_dir / "report.html"
        raw_html = template_file.read_text(encoding="utf-8")

        # Replace standard template tokens
        rendered = raw_html.replace("{{ summary.experiment_name }}", str(summary.get("experiment_name", "Experiment")))
        rendered = rendered.replace("{{ summary.fault_type }}", str(summary.get("fault_type", "fault")))
        rendered = rendered.replace("{{ generated_at }}", context["generated_at"])
        rendered = rendered.replace("{{ outcome }}", report.outcome)
        rendered = rendered.replace("{{ resilience_score }}", str(context["resilience_score"]))
        rendered = rendered.replace("{{ availability_percentage }}", str(context["availability_percentage"]))
        rendered = rendered.replace("{{ baseline_latency_ms }}", str(context["baseline_latency_ms"]))
        rendered = rendered.replace("{{ maximum_latency_ms }}", str(context["maximum_latency_ms"]))
        rec_dur_str = f"{report.recovery_time_seconds:.1f}s" if report.recovery_time_seconds is not None else "N/A"
        rendered = rendered.replace("{% if recovery_time_seconds %}{{ recovery_time_seconds }}s{% else %}N/A{% endif %}", rec_dur_str)

        # Replace recommendations loop block
        rec_html_items = []
        for r in (report.recommendations or []):
            rec_html_items.append(
                f'<div class="rec-item"><span class="rec-priority priority-{r.get("priority")}">{r.get("priority")}</span>'
                f'<strong>{r.get("category")}:</strong> {r.get("recommendation")}</div>'
            )
        recs_block = "\n".join(rec_html_items)

        start_tag = "{% for rec in recommendations %}"
        end_tag = "{% endfor %}"
        if start_tag in rendered and end_tag in rendered:
            prefix = rendered.split(start_tag)[0]
            suffix = rendered.split(end_tag)[1]
            rendered = prefix + recs_block + suffix

        return rendered

    def compare_service_experiments(self, service_id: uuid.UUID) -> Dict[str, Any]:
        """Compares historical resilience metrics and scores across experiments for a target service."""
        service = self.db.get(Service, service_id)
        service_name = service.name if service else "Unknown"

        stmt = (
            select(ExperimentReport)
            .join(Experiment, ExperimentReport.experiment_id == Experiment.id)
            .where(Experiment.service_id == service_id)
            .order_by(ExperimentReport.generated_at.desc())
        )
        reports = list(self.db.scalars(stmt).all())

        scores = [r.summary.get("resilience_score", 0.0) for r in reports if r.summary]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        experiments_summary: List[Dict[str, Any]] = [
            {
                "experiment_id": str(r.experiment_id),
                "outcome": r.outcome,
                "resilience_score": r.summary.get("resilience_score", 0.0),
                "fault_type": r.summary.get("fault_type", "unknown"),
                "availability": r.availability_percentage,
                "generated_at": r.generated_at.isoformat(),
            }
            for r in reports
        ]

        return {
            "target_service_id": str(service_id),
            "target_service_name": service_name,
            "total_experiments": len(reports),
            "average_resilience_score": round(avg_score, 1),
            "experiments": experiments_summary,
        }
