"""巡检 API"""

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/reports")
async def list_reports() -> dict[str, Any]:
    """列出巡检报告"""
    # TODO: 实现报告查询
    return {"reports": []}


@router.post("/run")
async def run_patrol() -> dict[str, Any]:
    """手动触发巡检"""
    # TODO: 实现巡检触发
    return {"status": "triggered", "message": "巡检已启动"}
