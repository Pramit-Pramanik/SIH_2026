from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from backend.app.core.config import get_settings
from backend.app.dependencies.get_db import get_db
from backend.app.schemas.health import HealthResponse, DatabaseStatus, RedisStatus

import time
from typing import Dict, Any

router = APIRouter(tags=["Health & Diagnostics"])
settings = get_settings()

_redis_health_cache: Dict[str, Any] = {"timestamp": 0.0, "status": None}

def _check_redis(redis_url: str) -> RedisStatus:
    now = time.time()
    cached = _redis_health_cache.get("status")
    if cached and (now - _redis_health_cache.get("timestamp", 0.0) < 3.0):
        return cached

    clean_url = redis_url.replace("localhost", "127.0.0.1")
    try:
        r = redis.from_url(
            clean_url,
            socket_timeout=0.2,
            socket_connect_timeout=0.2,
            retry_on_timeout=False
        )
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

    _redis_health_cache["timestamp"] = now
    _redis_health_cache["status"] = redis_status
    return redis_status

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
    redis_status = _check_redis(settings.REDIS_URL)

    if db_status.status != "connected" or redis_status.status != "connected":
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        database=db_status,
        redis=redis_status,
        version="0.1.0"
    )
