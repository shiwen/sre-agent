"""对话 API"""

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def chat(message: str) -> dict[str, Any]:
    """对话接口"""
    # TODO: 实现对话逻辑
    return {"response": f"收到消息: {message}", "status": "developing"}
