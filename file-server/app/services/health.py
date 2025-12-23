"""Health check service layer."""
import time
import psutil

from app.schemas.health import HealthResponse, DetailedHealthResponse, MetricsResponse, SystemMetrics
from app.utils.datetime_utils import now
from app.config.settings import settings


_start_time = time.time()


def get_uptime() -> float:
    """Get service uptime in seconds."""
    return round(time.time() - _start_time, 2)


def get_system_metrics() -> SystemMetrics:
    """Collect system resource metrics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    process = psutil.Process()
    
    return SystemMetrics(
        cpu={
            "usage_percent": cpu_percent,
            "count": psutil.cpu_count(),
        },
        memory={
            "total_mb": round(memory.total / 1024 / 1024, 2),
            "used_mb": round(memory.used / 1024 / 1024, 2),
            "available_mb": round(memory.available / 1024 / 1024, 2),
            "percent": memory.percent,
        },
        disk={
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
            "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
            "percent": disk.percent,
        },
        process={
            "open_files": len(process.open_files()),
            "num_threads": process.num_threads(),
        }
    )


async def get_basic_health() -> HealthResponse:
    """Get basic health status."""
    return HealthResponse(
        status="healthy",
        service="file-server",
        timestamp=now().isoformat(),
        uptime_seconds=get_uptime(),
        version="1.0.0",
    )


async def get_detailed_health() -> DetailedHealthResponse:
    """Get detailed health with component checks."""
    components = {}
    
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)}"
    
    try:
        from minio import Minio
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        list(client.list_buckets())
        components["minio"] = "healthy"
    except Exception as e:
        components["minio"] = f"unhealthy: {str(e)}"
    
    try:
        from pymilvus import connections
        connections.connect(
            alias="health_check",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        connections.disconnect("health_check")
        components["milvus"] = "healthy"
    except Exception as e:
        components["milvus"] = f"unhealthy: {str(e)}"
    
    try:
        import pika
        params = pika.URLParameters(settings.RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        connection.close()
        components["rabbitmq"] = "healthy"
    except Exception as e:
        components["rabbitmq"] = f"unhealthy: {str(e)}"
    
    worker_info = {
        "pool_size": settings.WORKER_POOL_SIZE,
        "queue_name": settings.RABBITMQ_QUEUE_NAME,
    }
    
    overall_status = "healthy" if all(
        v == "healthy" for v in components.values()
    ) else "degraded"
    
    return DetailedHealthResponse(
        status=overall_status,
        service="file-server",
        timestamp=now().isoformat(),
        uptime_seconds=get_uptime(),
        version="1.0.0",
        components=components,
        system=get_system_metrics(),
        workers=worker_info,
    )


def get_metrics() -> MetricsResponse:
    """Get service metrics for monitoring."""
    process = psutil.Process()
    
    return MetricsResponse(
        service_uptime_seconds=get_uptime(),
        cpu_usage_percent=psutil.cpu_percent(interval=0.1),
        memory_usage_bytes=process.memory_info().rss,
        memory_usage_percent=round(process.memory_percent(), 2),
        open_files=len(process.open_files()),
        num_threads=process.num_threads(),
        num_fds=process.num_fds() if hasattr(process, 'num_fds') else None,
        worker_pool_size=settings.WORKER_POOL_SIZE,
        timestamp=now().isoformat(),
    )
