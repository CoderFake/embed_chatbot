"""Health check service layer."""
import time
import psutil

from app.schemas.health import HealthResponse, DetailedHealthResponse, MetricsResponse, SystemMetrics
from app.utils.datetime_utils import now
from app.core.redis_client import redis_client
from app.services.queue_consumer import queue_consumer


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
        service="visitor-grader",
        timestamp=now().isoformat(),
        uptime_seconds=get_uptime(),
        version="1.0.0",
    )


async def get_detailed_health() -> DetailedHealthResponse:
    """Get detailed health with component checks."""
    
    
    components = {}
    
    try:
        await redis_client.client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)}"
    
    try:
        components["queue_consumer"] = "running" if queue_consumer._running else "stopped"
    except Exception as e:
        components["queue_consumer"] = f"error: {str(e)}"
    
    overall_status = "healthy" if all(
        v == "healthy" or v == "running" for v in components.values()
    ) else "degraded"
    
    return DetailedHealthResponse(
        status=overall_status,
        service="visitor-grader",
        timestamp=now().isoformat(),
        uptime_seconds=get_uptime(),
        version="1.0.0",
        components=components,
        system=get_system_metrics(),
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
        timestamp=now().isoformat(),
    )
