import time
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.schemas.health import HealthResponse, ServiceStatus

router = APIRouter(prefix="/health", tags=["Health Checks"])


@router.get("", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def check_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Comprehensive health check for API, PostgreSQL database, and ChromaDB vector store.
    """
    services_status = {}
    overall_healthy = True

    # 1. Database Check
    db_start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - db_start) * 1000
        services_status["database"] = ServiceStatus(
            status="healthy",
            latency_ms=round(db_latency, 2),
            details="Connected to PostgreSQL successfully"
        )
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        overall_healthy = False
        services_status["database"] = ServiceStatus(
            status="unreachable",
            latency_ms=None,
            details=f"PostgreSQL connection failed: {str(e)}"
        )

    # 2. ChromaDB Vector Store Check
    chroma_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.chroma_base_url}/api/v1/heartbeat")
            chroma_latency = (time.perf_counter() - chroma_start) * 1000
            if resp.status_code == 200:
                services_status["vector_store"] = ServiceStatus(
                    status="healthy",
                    latency_ms=round(chroma_latency, 2),
                    details="Connected to ChromaDB successfully"
                )
            else:
                overall_healthy = False
                services_status["vector_store"] = ServiceStatus(
                    status="degraded",
                    latency_ms=round(chroma_latency, 2),
                    details=f"ChromaDB returned status code {resp.status_code}"
                )
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")
        # Mark as degraded if not reachable in local dev
        services_status["vector_store"] = ServiceStatus(
            status="unreachable",
            latency_ms=None,
            details=f"ChromaDB connection failed: {str(e)}"
        )

    return HealthResponse(
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        status="healthy" if overall_healthy else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        services=services_status
    )


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Kubernetes / Docker simple liveness probe."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}
