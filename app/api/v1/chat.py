"""对话 API"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from structlog import get_logger

from app.agent.graph import run_agent
from app.agent.memory.session import get_session_manager
from app.agent.tools.base import register_all_tools

logger = get_logger()

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: str | None = None
    user_id: str | None = None


class ChatResponse(BaseModel):
    """对话响应"""
    response: str
    session_id: str
    structured_data: dict[str, Any] | None = None
    needs_approval: bool = False


def ensure_tools_registered() -> None:
    """确保工具已注册"""
    register_all_tools()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """处理对话请求"""
    ensure_tools_registered()

    result = await run_agent(
        user_query=request.message,
        session_id=request.session_id or "",
        user_id=request.user_id,
    )

    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"],
        structured_data=result.get("structured_data"),
        needs_approval=result.get("needs_approval", False),
    )


@router.get("/sessions")
async def list_sessions(user_id: str | None = None) -> dict[str, Any]:
    """列出会话"""
    manager = get_session_manager()
    sessions = manager.list_sessions(user_id)

    return {
        "sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "created_at": s.created_at.isoformat(),
                "message_count": len(s.messages),
                "status": s.status,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取会话详情"""
    manager = get_session_manager()
    session = manager.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "messages": [
            {"role": m.type, "content": m.content}
            for m in session.messages
        ],
        "summary": session.summary,
        "status": session.status,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除会话"""
    manager = get_session_manager()
    deleted = manager.delete(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": session_id}
