from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.monitoring.health_checker import HealthChecker
from app.services.service_registry import ServiceRegistry


def get_health_checker() -> HealthChecker:
    """Dependency for HealthChecker instance."""
    return HealthChecker()


def get_service_registry(
    db: Session = Depends(get_db),
    health_checker: HealthChecker = Depends(get_health_checker),
) -> ServiceRegistry:
    """Dependency that provides an initialized ServiceRegistry."""
    return ServiceRegistry(db=db, health_checker=health_checker)
