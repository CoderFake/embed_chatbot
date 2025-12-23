"""Health check schemas."""
from typing import Dict, Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Basic health check response."""
    status: str
    service: str
    timestamp: str
    uptime_seconds: float
    version: str


class SystemMetrics(BaseModel):
    """System resource metrics."""
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    process: Dict[str, Any]


class DetailedHealthResponse(BaseModel):
    """Detailed health check with components and system metrics."""
    status: str
    service: str
    timestamp: str
    uptime_seconds: float
    version: str
    components: Dict[str, str]
    system: SystemMetrics


class MetricsResponse(BaseModel):
    """Service metrics for monitoring."""
    service_uptime_seconds: float
    cpu_usage_percent: float
    memory_usage_bytes: int
    memory_usage_percent: float
    open_files: int
    num_threads: int
    num_fds: int | None
    timestamp: str
