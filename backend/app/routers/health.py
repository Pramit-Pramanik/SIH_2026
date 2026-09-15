from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from backend.app.core.config import get_settings
from backend.app.dependencies.get_db import get_db
from backend.app.schemas.health import HealthResponse, DatabaseStatus, RedisStatus

router = APIRouter(tags=["Health & Diagnostics"])
settings = get_settings()

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Connectivity Check",
    description="Validates relational database connectivity and Redis operational state."
)
def check_health(db: Session = Depends(get_db)) -> HealthResponse:
    # 1. Database check
    db_engine = db.bind.dialect.name if db.bind else "unknown"
    try:
        db.execute(text("SELECT 1"))
        db_status = DatabaseStatus(
            status="connected",
            engine=db_engine,
            details="Database ping succeeded"
        )
    except Exception as e:
        db_status = DatabaseStatus(
            status="error",
            engine=db_engine,
            details=str(e)
        )

    # 2. Redis check
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1.0, socket_connect_timeout=1.0)
        r.ping()
        redis_status = RedisStatus(
            status="connected",
            details="Redis ping acknowledged"
        )
    except Exception as e:
        redis_status = RedisStatus(
            status="disconnected",
            details=f"Redis unavailable: {type(e).__name__}"
        )

    overall_status = "healthy" if db_status.status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        database=db_status,
        redis=redis_status,
        version="0.1.0"
    )
