"""YuniKorn 队列 API"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from structlog import get_logger

from app.agent.tools.base import register_all_tools
from app.agent.tools.yunikorn import (
    YuniKornApplicationsTool,
    YuniKornQueueGetTool,
    YuniKornQueueListTool,
)

logger = get_logger()

router = APIRouter(prefix="/queues", tags=["queues"])


# 初始化工具
_queue_list_tool: YuniKornQueueListTool | None = None
_queue_get_tool: YuniKornQueueGetTool | None = None
_queue_apps_tool: YuniKornApplicationsTool | None = None


def get_queue_tools() -> tuple[YuniKornQueueListTool, YuniKornQueueGetTool, YuniKornApplicationsTool]:
    """延迟初始化工具"""
    global _queue_list_tool, _queue_get_tool, _queue_apps_tool
    if _queue_list_tool is None:
        register_all_tools()
        _queue_list_tool = YuniKornQueueListTool()
        _queue_get_tool = YuniKornQueueGetTool()
        _queue_apps_tool = YuniKornApplicationsTool()
    return _queue_list_tool, _queue_get_tool, _queue_apps_tool


@router.get("")
async def list_queues(
    partition: str = Query(default="default", description="分区名称"),
) -> dict[str, Any]:
    """列出所有队列"""
    queue_list, _, _ = get_queue_tools()

    result = queue_list.execute({
        "partition": partition,
    })

    return result


@router.get("/{queue_name}")
async def get_queue(
    queue_name: str,
    partition: str = Query(default="default", description="分区名称"),
) -> dict[str, Any]:
    """获取队列详情"""
    _, queue_get, _ = get_queue_tools()

    result = queue_get.execute({
        "queue_name": queue_name,
        "partition": partition,
    })

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{queue_name}/applications")
async def list_queue_applications(
    queue_name: str,
    partition: str = Query(default="default", description="分区名称"),
    state: str | None = Query(default=None, description="状态过滤"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量限制"),
) -> dict[str, Any]:
    """获取队列中的应用"""
    _, _, queue_apps = get_queue_tools()

    result = queue_apps.execute({
        "queue_name": queue_name,
        "partition": partition,
        "state": state,
        "limit": limit,
    })

    return result


@router.get("/health")
async def get_queue_health() -> dict[str, Any]:
    """获取队列健康状态概览"""
    queue_list, _, _ = get_queue_tools()

    result = queue_list.execute({"partition": "default"})

    queues = result.get("queues", [])

    # 统计健康状态
    critical_queues = [q for q in queues if q.get("utilization", 0) > 90]
    warning_queues = [q for q in queues if q.get("utilization", 0) > 70]

    return {
        "status": "ok" if not critical_queues else "warning",
        "queues": {
            "total": len(queues),
            "critical": len(critical_queues),
            "warning": len(warning_queues),
            "healthy": len(queues) - len(critical_queues) - len(warning_queues),
        },
    }
