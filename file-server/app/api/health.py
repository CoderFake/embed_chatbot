"""Health check and monitoring endpoints."""
from fastapi import APIRouter

from app.schemas.health import HealthResponse, DetailedHealthResponse, MetricsResponse
from app.services import health as health_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    Returns 200 if service is running.
    """
    return await health_service.get_basic_health()


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check() -> DetailedHealthResponse:
    """
    Detailed health check with component status and system metrics.
    Checks: Redis, MinIO, Milvus, RabbitMQ, Worker Pool, system resources.
    """
    return await health_service.get_detailed_health()


@router.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    """
    Prometheus-style metrics endpoint.
    Returns service metrics in JSON format.
    """
    return health_service.get_metrics()

