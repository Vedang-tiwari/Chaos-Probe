import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import ServiceAlreadyExistsError, ServiceNotFoundError
from app.core.logging import logger
from app.database.models.service import Service
from app.monitoring.health_checker import HealthCheckResult, HealthChecker
from app.schemas.service import ServiceCreate, ServiceUpdate


class ServiceRegistry:
    """Manages service registration, updates, retrieval, and health status tracking."""

    def __init__(self, db: Session, health_checker: Optional[HealthChecker] = None):
        self.db = db
        self.health_checker = health_checker or HealthChecker()

    def register_service(self, service_in: ServiceCreate) -> Service:
        """Registers a new target service. Ensures service name is unique."""
        existing = self.get_by_name(service_in.name)
        if existing:
            raise ServiceAlreadyExistsError(
                f"A service with name '{service_in.name}' is already registered.",
                details={"name": service_in.name, "existing_id": str(existing.id)},
            )

        db_service = Service(
            name=service_in.name,
            description=service_in.description,
            base_url=str(service_in.base_url),
            health_check_url=str(service_in.health_check_url),
            container_id=service_in.container_id,
            environment=service_in.environment,
            status="UNKNOWN",
        )
        self.db.add(db_service)
        self.db.commit()
        self.db.refresh(db_service)
        logger.info(f"Registered new target service: {db_service.name} (id={db_service.id})")
        return db_service

    def get_by_id(self, service_id: uuid.UUID) -> Service:
        """Retrieves a service by its unique UUID."""
        service = self.db.get(Service, service_id)
        if not service:
            raise ServiceNotFoundError(
                f"Service with id '{service_id}' was not found.",
                details={"service_id": str(service_id)},
            )
        return service

    def get_by_name(self, name: str) -> Optional[Service]:
        """Retrieves a service by name if it exists."""
        stmt = select(Service).where(Service.name == name)
        return self.db.scalars(stmt).first()

    def list_services(
        self,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Service]:
        """Returns a list of registered services with optional filters."""
        stmt = select(Service)
        if environment:
            stmt = stmt.where(Service.environment == environment)
        if status:
            stmt = stmt.where(Service.status == status)
        stmt = stmt.limit(limit).offset(offset).order_by(Service.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def update_service(self, service_id: uuid.UUID, update_in: ServiceUpdate) -> Service:
        """Updates service attributes."""
        service = self.get_by_id(service_id)

        update_data = update_in.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] != service.name:
            existing = self.get_by_name(update_data["name"])
            if existing and existing.id != service_id:
                raise ServiceAlreadyExistsError(
                    f"A service named '{update_data['name']}' already exists."
                )

        for field, value in update_data.items():
            setattr(service, field, value)

        self.db.commit()
        self.db.refresh(service)
        logger.info(f"Updated service: {service.name} (id={service.id})")
        return service

    def delete_service(self, service_id: uuid.UUID) -> None:
        """Deletes a registered service from the registry."""
        service = self.get_by_id(service_id)
        self.db.delete(service)
        self.db.commit()
        logger.info(f"Deleted service: {service.name} (id={service_id})")

    async def check_service_health(self, service_id: uuid.UUID) -> HealthCheckResult:
        """Probes the service health endpoint and persists the updated status in the database."""
        service = self.get_by_id(service_id)
        result = await self.health_checker.check_http_endpoint(
            service_id=service.id,
            service_name=service.name,
            health_check_url=service.health_check_url,
        )

        # Update service status in DB
        service.status = result.status
        self.db.commit()
        self.db.refresh(service)
        return result
