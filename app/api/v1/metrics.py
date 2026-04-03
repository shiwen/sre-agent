"""Prometheus Metrics API Endpoint"""

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.infrastructure.metrics_exporter import get_metrics_registry, get_metrics_collector
from structlog import get_logger

logger = get_logger()

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_class=PlainTextResponse)
async def get_metrics() -> Response:
    """获取 Prometheus 格式的指标

    Returns:
        Prometheus text format metrics
    """
    registry = get_metrics_registry()
    metrics_text = registry.export_prometheus_format()

    logger.debug("metrics_exported", size=len(metrics_text))

    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/summary")
async def get_metrics_summary() -> dict:
    """获取指标摘要

    Returns:
        Metrics summary including counts and types
    """
    registry = get_metrics_registry()
    return registry.get_summary()


@router.post("/clear")
async def clear_metrics() -> dict:
    """清除所有指标值

    Returns:
        Success status
    """
    registry = get_metrics_registry()
    registry.clear()

    logger.info("metrics_cleared")

    return {"status": "ok", "message": "Metrics cleared"}


@router.get("/definitions")
async def get_metric_definitions() -> list[dict]:
    """获取所有指标定义

    Returns:
        List of metric definitions
    """
    registry = get_metrics_registry()
    metrics = registry.get_all_metrics()

    return [
        {
            "name": m.name,
            "type": m.type.value,
            "description": m.description,
            "unit": m.unit,
            "labels": m.labels,
        }
        for m in metrics
    ]