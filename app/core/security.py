from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_admin_key(api_key: str | None = Security(API_KEY_HEADER)) -> bool:
    """Verifies that the provided API key matches the configured ADMIN_API_KEY."""
    settings = get_settings()
    if not settings.ADMIN_API_KEY:
        # In open development without configured admin key, allow with warning
        return True

    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing administrator API key.",
        )
    return True
