"""
System monitoring API routes - Real server metrics, performance data, and logs.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from collections import deque

import psutil
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

# Track server start time
_server_start_time = time.time()

# In-memory log buffer (ring buffer of recent logs)
_log_buffer: deque = deque(maxlen=500)


def add_system_log(level: str, message: str, details: str = "", source: str = "system"):
    """Add a log entry to the in-memory buffer. Call this from anywhere in the app."""
    _log_buffer.append({
        "id": len(_log_buffer),
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "details": details,
        "source": source,
    })


# Seed a startup log
add_system_log("info", "System monitoring module loaded", "Routes registered")


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ResourceInfo(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_used_gb: float
    memory_total_gb: float
    memory_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    network_sent_mb_s: float
    network_recv_mb_s: float


class ServiceStatus(BaseModel):
    name: str
    status: str  # "online" | "offline" | "degraded"
    metrics: List[Dict[str, str]]


class SystemStatusResponse(BaseModel):
    uptime_seconds: int
    server_start_time: str
    resources: ResourceInfo
    services: List[ServiceStatus]
    active_connections: int
    python_version: str
    pid: int


class PerformancePoint(BaseModel):
    time: str
    cpu: float
    memory: float
    disk_io_read: float
    disk_io_write: float


class PerformanceResponse(BaseModel):
    data_points: List[PerformancePoint]
    summary: Dict[str, Any]


class LogEntry(BaseModel):
    id: int
    timestamp: str
    level: str
    message: str
    details: str
    source: str


class LogsResponse(BaseModel):
    logs: List[LogEntry]
    total: int


# ============================================================================
# Network I/O tracker (to compute rates)
# ============================================================================

_last_net_io = None
_last_net_time = None


def _get_network_rates() -> tuple[float, float]:
    """Return (recv_mb_s, sent_mb_s) based on delta from last call."""
    global _last_net_io, _last_net_time
    counters = psutil.net_io_counters()
    now = time.time()
    if _last_net_io is None or _last_net_time is None:
        _last_net_io = counters
        _last_net_time = now
        return (0.0, 0.0)
    dt = now - _last_net_time
    if dt < 0.1:
        dt = 0.1
    recv_rate = (counters.bytes_recv - _last_net_io.bytes_recv) / dt / (1024 * 1024)
    sent_rate = (counters.bytes_sent - _last_net_io.bytes_sent) / dt / (1024 * 1024)
    _last_net_io = counters
    _last_net_time = now
    return (max(0.0, round(recv_rate, 2)), max(0.0, round(sent_rate, 2)))


# ============================================================================
# Performance history buffer
# ============================================================================

_perf_history: deque = deque(maxlen=60)
_last_perf_collect = 0.0
_last_disk_io = None
_last_disk_time = None


def _collect_performance_snapshot():
    """Collect a performance snapshot. Called on-demand, throttled to 1/sec."""
    global _last_perf_collect, _last_disk_io, _last_disk_time
    now = time.time()
    if now - _last_perf_collect < 1.0 and len(_perf_history) > 0:
        return
    _last_perf_collect = now

    cpu = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory().percent

    # Disk I/O rates
    disk_io = psutil.disk_io_counters()
    read_rate = 0.0
    write_rate = 0.0
    if disk_io and _last_disk_io and _last_disk_time:
        dt = now - _last_disk_time
        if dt > 0.1:
            read_rate = (disk_io.read_bytes - _last_disk_io.read_bytes) / dt / (1024 * 1024)
            write_rate = (disk_io.write_bytes - _last_disk_io.write_bytes) / dt / (1024 * 1024)
    if disk_io:
        _last_disk_io = disk_io
        _last_disk_time = now

    _perf_history.append(PerformancePoint(
        time=datetime.utcnow().strftime("%H:%M:%S"),
        cpu=round(cpu, 1),
        memory=round(mem, 1),
        disk_io_read=round(max(0, read_rate), 2),
        disk_io_write=round(max(0, write_rate), 2),
    ))


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Get real-time system status including CPU, memory, disk, network,
    and service health.
    """
    process = psutil.Process(os.getpid())
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    recv_rate, sent_rate = _get_network_rates()

    resources = ResourceInfo(
        cpu_percent=round(psutil.cpu_percent(interval=0), 1),
        cpu_count=psutil.cpu_count() or 1,
        memory_used_gb=round(mem.used / (1024 ** 3), 2),
        memory_total_gb=round(mem.total / (1024 ** 3), 2),
        memory_percent=round(mem.percent, 1),
        disk_used_gb=round(disk.used / (1024 ** 3), 1),
        disk_total_gb=round(disk.total / (1024 ** 3), 1),
        disk_percent=round(disk.percent, 1),
        network_sent_mb_s=sent_rate,
        network_recv_mb_s=recv_rate,
    )

    # Check services
    services = await _check_services()

    uptime_s = int(time.time() - _server_start_time)

    import sys
    return SystemStatusResponse(
        uptime_seconds=uptime_s,
        server_start_time=datetime.utcfromtimestamp(_server_start_time).isoformat(),
        resources=resources,
        services=services,
        active_connections=len(psutil.Process(os.getpid()).connections()),
        python_version=sys.version.split()[0],
        pid=os.getpid(),
    )


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance_data(
    points: int = Query(default=30, le=60, description="Number of data points to return"),
):
    """
    Get recent performance time-series data (CPU, memory, disk I/O).
    Each call also records a new data point.
    """
    _collect_performance_snapshot()

    data = list(_perf_history)[-points:]

    # Summary
    if data:
        avg_cpu = round(sum(p.cpu for p in data) / len(data), 1)
        avg_mem = round(sum(p.memory for p in data) / len(data), 1)
        max_cpu = round(max(p.cpu for p in data), 1)
        max_mem = round(max(p.memory for p in data), 1)
    else:
        avg_cpu = avg_mem = max_cpu = max_mem = 0.0

    return PerformanceResponse(
        data_points=data,
        summary={
            "avg_cpu": avg_cpu,
            "avg_memory": avg_mem,
            "max_cpu": max_cpu,
            "max_memory": max_mem,
            "data_point_count": len(data),
        },
    )


@router.get("/logs", response_model=LogsResponse)
async def get_system_logs(
    level: Optional[str] = Query(None, description="Filter by level: info, warn, error, success, debug, system"),
    search: Optional[str] = Query(None, description="Search in message or details"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Get system logs from the in-memory buffer.
    """
    logs = list(_log_buffer)

    # Filter by level
    if level:
        logs = [l for l in logs if l["level"] == level]

    # Filter by search
    if search:
        search_lower = search.lower()
        logs = [l for l in logs if search_lower in l["message"].lower() or search_lower in l.get("details", "").lower()]

    total = len(logs)

    # Apply offset and limit (newest first)
    logs = list(reversed(logs))[offset:offset + limit]

    return LogsResponse(
        logs=[LogEntry(**l) for l in logs],
        total=total,
    )


# ============================================================================
# SERVICE CHECKS
# ============================================================================

async def _check_services() -> List[ServiceStatus]:
    """Check the status of backend services."""
    services = []

    # 1. API Server (we are running, so always online)
    process = psutil.Process(os.getpid())
    proc_mem = process.memory_info()
    services.append(ServiceStatus(
        name="API Server",
        status="online",
        metrics=[
            {"label": "PID", "value": str(os.getpid())},
            {"label": "Memory", "value": f"{round(proc_mem.rss / (1024 ** 2))}MB"},
        ],
    ))

    # 2. Database
    db_status = "offline"
    db_metrics = [{"label": "Status", "value": "unreachable"}]
    try:
        from mind.core.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            start = time.time()
            await session.execute(text("SELECT 1"))
            latency = round((time.time() - start) * 1000)
            db_status = "online"
            db_metrics = [
                {"label": "Latency", "value": f"{latency}ms"},
                {"label": "Status", "value": "connected"},
            ]
    except Exception as e:
        db_metrics = [{"label": "Error", "value": str(e)[:50]}]

    services.append(ServiceStatus(name="Database", status=db_status, metrics=db_metrics))

    # 3. Redis
    redis_status = "offline"
    redis_metrics = [{"label": "Status", "value": "unreachable"}]
    try:
        import redis.asyncio as aioredis
        from mind.config.settings import settings as app_settings
        r = aioredis.from_url(app_settings.REDIS_URL if hasattr(app_settings, 'REDIS_URL') else "redis://localhost:6379")
        start = time.time()
        await r.ping()
        latency = round((time.time() - start) * 1000)
        info = await r.info("memory")
        used_mem = info.get("used_memory_human", "N/A")
        redis_status = "online"
        redis_metrics = [
            {"label": "Latency", "value": f"{latency}ms"},
            {"label": "Memory", "value": str(used_mem)},
        ]
        await r.aclose()
    except Exception:
        redis_metrics = [{"label": "Status", "value": "unavailable"}]

    services.append(ServiceStatus(name="Redis Cache", status=redis_status, metrics=redis_metrics))

    # 4. LLM Service
    llm_status = "offline"
    llm_metrics = [{"label": "Status", "value": "unreachable"}]
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            start = time.time()
            resp = await client.get("http://localhost:11434/api/tags")
            latency = round((time.time() - start) * 1000)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                llm_status = "online"
                llm_metrics = [
                    {"label": "Latency", "value": f"{latency}ms"},
                    {"label": "Models", "value": str(len(models))},
                ]
            else:
                llm_status = "degraded"
                llm_metrics = [{"label": "HTTP", "value": str(resp.status_code)}]
    except Exception:
        llm_metrics = [{"label": "Status", "value": "unavailable"}]

    services.append(ServiceStatus(name="LLM Service", status=llm_status, metrics=llm_metrics))

    # 5. Activity Engine
    engine_status = "offline"
    engine_metrics = [{"label": "Status", "value": "not running"}]
    try:
        from mind.engine.activity_engine import get_activity_engine
        engine = get_activity_engine()
        if engine:
            engine_status = "online"
            engine_metrics = [
                {"label": "Status", "value": "running"},
            ]
    except Exception:
        pass

    services.append(ServiceStatus(name="Activity Engine", status=engine_status, metrics=engine_metrics))

    return services
