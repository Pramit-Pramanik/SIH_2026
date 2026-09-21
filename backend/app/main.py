from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow the documented ``uvicorn app.main:app`` command from backend/ while
# retaining repository-root imports everywhere else.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.core.config import get_settings
from backend.app.routers.health import router as health_router
from backend.app.routers.mock_ekyc import router as mock_ekyc_router
from backend.app.routers.slots import router as slots_router
from backend.app.routers.gate import router as gate_router
from backend.app.routers.quality import router as quality_router
from backend.app.routers.queue import router as queue_router
from backend.app.routers.weighbridge import router as weighbridge_router
from backend.app.routers.billing import router as billing_router
from backend.app.routers.payout import router as payout_router
from backend.app.routers.mock_dbt import router as mock_dbt_router
from backend.app.routers.sync import router as sync_router
from backend.app.routers.ussd import router as ussd_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.mandis import router as mandis_router
from backend.app.routers.crops import router as crops_router
from backend.app.routers.farmers import router as farmers_router
from backend.app.routers.admin import router as admin_router
from backend.app.routers.transactions import router as transactions_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Validates fail-closed security configuration. Alembic is responsible for
    creating and upgrading application schemas outside isolated tests.
    """
    # 1. Enforce fail-closed cryptographic key safety unless in test environment
    settings.validate_secrets()

    # Note: Database schema management is authoritatively handled by Alembic migrations.
    # Application startup does not silently create or alter schemas outside migration control.

    yield

    # Clean shutdown logic if needed

app = FastAPI(
    title="MandiQ Platform API",
    description="Intelligent APMC Yard & Dynamic Queue Management Platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(health_router)
app.include_router(health_router, prefix="/api/v1")
app.include_router(mock_ekyc_router, prefix="/api/v1")
app.include_router(slots_router, prefix="/api/v1")
app.include_router(gate_router, prefix="/api/v1")
app.include_router(quality_router, prefix="/api/v1")
app.include_router(queue_router, prefix="/api/v1")
app.include_router(weighbridge_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(payout_router, prefix="/api/v1")
app.include_router(mock_dbt_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(ussd_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(mandis_router, prefix="/api/v1")
app.include_router(crops_router, prefix="/api/v1")
app.include_router(farmers_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
def root() -> JSONResponse:
    return JSONResponse(
        content={
            "platform": "MandiQ",
            "tagline": "Intelligent APMC Yard & Dynamic Queue Management",
            "version": "0.1.0",
            "status": "online",
            "documentation": "/docs"
        }
    )
