from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str = Field(..., description="Status of the service component (healthy, degraded, unreachable)")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    details: Optional[str] = Field(None, description="Optional diagnostic details or error message")


class HealthResponse(BaseModel):
    app_name: str
    environment: str
    status: str = Field(..., description="Overall health status (healthy, degraded, unhealthy)")
    timestamp: datetime
    version: str = "1.0.0"
    services: Dict[str, ServiceStatus]
