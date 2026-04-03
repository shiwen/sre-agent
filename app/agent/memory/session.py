"""会话管理器"""

from datetime import datetime
import hashlib
import json
from typing import Any
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from structlog import get_logger

from app.agent.llm.registry import get_llm_registry

logger = get_logger()


class Session(BaseModel):
    """会话状态"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "anonymous"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 消息历史
    messages: list[BaseMessage] = Field(default_factory=list)

    # 上下文摘要（Token 控制）
    summary: str | None = None

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 状态
    status: str = "active"  # active, paused, completed

    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_context_string(self) -> str:
        """获取上下文字符串（用于 LLM）"""
        parts = []

        if self.summary:
            parts.append(f"历史摘要: {self.summary}")

        for msg in self.messages[-10:]:
            if isinstance(msg, HumanMessage):
                parts.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                parts.append(f"助手: {msg.content}")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [
                {"type": msg.type, "content": msg.content}
                for msg in self.messages
            ],
            "summary": self.summary,
            "metadata": self.metadata,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """从字典恢复"""
        messages = []
        for msg_data in data.get("messages", []):
            if msg_data["type"] == "human":
                messages.append(HumanMessage(content=msg_data["content"]))
            elif msg_data["type"] == "ai":
                messages.append(AIMessage(content=msg_data["content"]))

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=messages,
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
            status=data.get("status", "active"),
        )


class SessionManager:
    """会话管理器"""

    SUMMARY_THRESHOLD = 10  # 消息数超过此值时生成摘要

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        # TODO: K8s ConfigMap 持久化客户端

    def create(self, user_id: str | None = None) -> Session:
        """创建新会话"""
        session = Session(
            user_id=user_id or "anonymous",
        )
        self._sessions[session.id] = session
        logger.info("session_created", session_id=session.id, user_id=user_id)
        return session

    def get(self, session_id: str) -> Session | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def get_or_create(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> Session:
        """获取或创建会话"""
        if session_id:
            session = self._sessions.get(session_id)
            if session:
                return session

        return self.create(user_id)

    def save(self, session: Session) -> None:
        """保存会话"""
        self._sessions[session.id] = session
        # TODO: 异步持久化到 K8s ConfigMap
        logger.debug("session_saved", session_id=session.id)

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("session_deleted", session_id=session_id)
            return True
        return False

    def list_sessions(self, user_id: str | None = None) -> list[Session]:
        """列出会话"""
        if user_id:
            return [s for s in self._sessions.values() if s.user_id == user_id]
        return list(self._sessions.values())

    async def summarize_if_needed(self, session: Session) -> None:
        """滚动摘要压缩"""
        if len(session.messages) <= self.SUMMARY_THRESHOLD:
            return

        # 获取需要摘要的消息
        messages_to_summarize = session.messages[:-self.SUMMARY_THRESHOLD]

        # 调用 LLM 生成摘要
        try:
            llm_registry = get_llm_registry()
            summary = await llm_registry.summarize(messages_to_summarize)

            # 更新会话
            session.messages = session.messages[-self.SUMMARY_THRESHOLD:]
            session.summary = summary
            self.save(session)

            logger.info(
                "session_summarized",
                session_id=session.id,
                messages_kept=len(session.messages),
            )

        except Exception as e:
            logger.error("summarization_failed", error=str(e))

    def get_hash(self, session: Session) -> str:
        """计算会话哈希（用于检查点）"""
        content = json.dumps(session.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# 全局实例
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取全局 Session Manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
