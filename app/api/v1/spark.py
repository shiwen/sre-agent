"""Spark API"""

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/apps")
async def list_apps(namespace: str = "default") -> dict[str, Any]:
    """列出 Spark 应用"""
    # TODO: 实现 Spark 应用查询
    return {"applications": [], "namespace": namespace}


@router.get("/apps/{name}")
async def get_app(name: str, namespace: str = "default") -> dict[str, Any]:
    """获取 Spark 应用详情"""
    # TODO: 实现应用详情查询
    return {"name": name, "namespace": namespace, "status": "developing"}
