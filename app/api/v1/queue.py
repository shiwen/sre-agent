"""队列 API"""

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_queues() -> dict[str, Any]:
    """列出 YuniKorn 队列"""
    # TODO: 实现队列查询
    return {"queues": []}


@router.get("/{name}")
async def get_queue(name: str) -> dict[str, Any]:
    """获取队列详情"""
    # TODO: 实现队列详情查询
    return {"name": name, "utilization": "developing"}
