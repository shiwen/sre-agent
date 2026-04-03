"""Spark API"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from structlog import get_logger

from app.agent.tools.base import register_all_tools
from app.agent.tools.spark import (
    SparkAnalyzeTool,
    SparkGetTool,
    SparkListTool,
    SparkLogsTool,
)

logger = get_logger()

router = APIRouter(prefix="/spark", tags=["spark"])


class AnalyzeRequest(BaseModel):
    """分析请求"""
    app_name: str
    namespace: str = "default"


# 初始化工具
_spark_list_tool: SparkListTool | None = None
_spark_get_tool: SparkGetTool | None = None
_spark_logs_tool: SparkLogsTool | None = None
_spark_analyze_tool: SparkAnalyzeTool | None = None


def get_tools() -> tuple[SparkListTool, SparkGetTool, SparkLogsTool, SparkAnalyzeTool]:
    """延迟初始化工具"""
    global _spark_list_tool, _spark_get_tool, _spark_logs_tool, _spark_analyze_tool
    if _spark_list_tool is None:
        register_all_tools()
        _spark_list_tool = SparkListTool()
        _spark_get_tool = SparkGetTool()
        _spark_logs_tool = SparkLogsTool()
        _spark_analyze_tool = SparkAnalyzeTool()
    return _spark_list_tool, _spark_get_tool, _spark_logs_tool, _spark_analyze_tool


@router.get("/apps")
async def list_apps(
    namespace: str = Query(default=None, description="命名空间过滤"),
    status: str | None = Query(default=None, description="状态过滤"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量限制"),
) -> dict[str, Any]:
    """列出 Spark 应用"""
    spark_list, _, _, _ = get_tools()

    status_list = [status] if status else None

    result = spark_list.execute({
        "namespace": namespace,
        "status": status_list,
        "limit": limit,
    })

    return result


@router.get("/apps/{name}")
async def get_app(
    name: str,
    namespace: str = Query(default="default", description="命名空间"),
) -> dict[str, Any]:
    """获取 Spark 应用详情"""
    _, spark_get, _, _ = get_tools()

    result = spark_get.execute({
        "app_name": name,
        "namespace": namespace,
    })

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/apps/{name}/logs")
async def get_logs(
    name: str,
    namespace: str = Query(default="default", description="命名空间"),
    pod_type: str = Query(default="driver", description="Pod 类型: driver/executor"),
    tail_lines: int = Query(default=500, ge=1, le=2000, description="日志行数"),
) -> dict[str, Any]:
    """获取 Spark 应用日志"""
    _, _, spark_logs, _ = get_tools()

    result = spark_logs.execute({
        "app_name": name,
        "namespace": namespace,
        "pod_type": pod_type,
        "tail_lines": tail_lines,
    })

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/apps/{name}/analyze")
async def analyze_app(
    name: str,
    namespace: str = Query(default="default", description="命名空间"),
) -> dict[str, Any]:
    """分析 Spark 应用日志"""
    _, _, _, spark_analyze = get_tools()

    result = spark_analyze.execute({
        "app_name": name,
        "namespace": namespace,
    })

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/analyze-batch")
async def analyze_batch(request: AnalyzeRequest) -> dict[str, Any]:
    """批量分析失败应用"""
    spark_list, _, _, spark_analyze = get_tools()

    # 获取失败应用列表
    failures = spark_list.execute({
        "namespace": request.namespace,
        "status": ["FAILED"],
        "limit": 20,
    })

    # 分析失败模式
    result = spark_analyze.execute({
        "recent_failures": failures,
    })

    return result
