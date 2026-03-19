"""
Metrics and health check API routes.
Provides Prometheus metrics endpoint and health status endpoints.
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from mind.monitoring.metrics import get_metrics
from mind.monitoring.health import get_health_checker, HealthState

router = APIRouter(tags=["health"])


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Returns all Prometheus metrics in text format for scraping",
    response_class=Response,
)
async def prometheus_metrics():
    """
    Get Prometheus metrics.

    Returns all collected metrics in Prometheus text format,
    suitable for scraping by Prometheus server.
    """
    metrics_data = get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get(
    "/health",
    summary="Detailed Health Check",
    description="Returns comprehensive health status of all system components",
)
async def detailed_health_check():
    """
    Get detailed health status.

    Performs health checks on all system components:
    - Database connectivity
    - Redis connectivity
    - Ollama LLM service
    - WebSocket manager

    Returns:
        JSON with detailed health status for each component
    """
    health_checker = get_health_checker()
    system_health = await health_checker.get_system_health()

    status_code = 200
    if system_health.status == HealthState.UNHEALTHY:
        status_code = 503
    elif system_health.status == HealthState.DEGRADED:
        status_code = 200  # Still return 200 for degraded, but indicate in body

    return JSONResponse(
        content=system_health.to_dict(),
        status_code=status_code,
    )


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Simple liveness check - returns 200 if the service is running",
)
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.

    Returns 200 OK if the application is running.
    This endpoint should always succeed if the process is alive.
    """
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Checks if the service is ready to accept traffic",
)
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.

    Checks critical dependencies (database, LLM) and returns:
    - 200 if ready to serve traffic
    - 503 if not ready

    This endpoint is used by load balancers to determine if
    the instance should receive traffic.
    """
    health_checker = get_health_checker()

    # Only check critical services for readiness
    db_health = await health_checker.check_database()
    ollama_health = await health_checker.check_ollama()

    is_ready = (
        db_health.status != HealthState.UNHEALTHY and
        ollama_health.status != HealthState.UNHEALTHY
    )

    if is_ready:
        return JSONResponse(
            content={
                "status": "ready",
                "checks": {
                    "database": db_health.status.value,
                    "ollama": ollama_health.status.value,
                },
            },
            status_code=200,
        )
    else:
        return JSONResponse(
            content={
                "status": "not_ready",
                "checks": {
                    "database": db_health.to_dict(),
                    "ollama": ollama_health.to_dict(),
                },
            },
            status_code=503,
        )
