from typing import Dict, Any, Optional
from pydantic import BaseModel

class DatabaseStatus(BaseModel):
    status: str
    engine: str
    details: Optional[str] = None

class RedisStatus(BaseModel):
    status: str
    details: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    environment: str
    database: DatabaseStatus
    redis: RedisStatus
    version: str = "0.1.0"
