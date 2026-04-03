"""会话管理器"""

from datetime import datetime
from functools import wraps
import hashlib
import json
from typing import Any, Callable
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from structlog import get_logger

from app.agent.llm.registry import get_llm_registry

logger = get_logger()

# K8s 客户端（可选依赖）
try:
    from kubernetes import client, config
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    logger.warning("kubernetes_not_available", fallback="memory_storage")


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


def handle_k8s_errors(func: Callable) -> Callable:
    """K8s 错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not KUBERNETES_AVAILABLE:
            return None
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "ConfigException" in str(type(e).__name__):
                logger.warning("k8s_config_not_found", fallback="memory")
            else:
                logger.warning("k8s_error", error=str(e), fallback="memory")
            return None
    return wrapper


class SessionManager:
    """会话管理器（支持 K8s ConfigMap 持久化）"""

    SUMMARY_THRESHOLD = 10  # 消息数超过此值时生成摘要
    CONFIGMAP_NAME = "sre-agent-sessions"
    CONFIGMAP_NAMESPACE = "default"

    def __init__(self, use_k8s: bool = True) -> None:
        self._sessions: dict[str, Session] = {}
        self._k8s_available = False
        self._k8s_core_v1 = None

        if use_k8s and KUBERNETES_AVAILABLE:
            self._init_k8s_client()

    def _init_k8s_client(self) -> None:
        """初始化 K8s 客户端"""
        try:
            # 尝试加载 K8s 配置
            try:
                config.load_incluster_config()
                logger.info("k8s_incluster_config_loaded")
            except config.ConfigException:
                config.load_kube_config()
                logger.info("k8s_kubeconfig_loaded")

            self._k8s_core_v1 = client.CoreV1Api()
            self._k8s_available = True

            # 确保 ConfigMap 存在
            self._ensure_configmap()

        except Exception as e:
            logger.warning("k8s_init_failed", error=str(e), fallback="memory")
            self._k8s_available = False

    @handle_k8s_errors
    def _ensure_configmap(self) -> None:
        """确保 ConfigMap 存在"""
        try:
            self._k8s_core_v1.read_namespaced_config_map(
                name=self.CONFIGMAP_NAME,
                namespace=self.CONFIGMAP_NAMESPACE,
            )
        except client.exceptions.ApiException as e:
            if e.status == 404:
                # 创建 ConfigMap
                self._k8s_core_v1.create_namespaced_config_map(
                    namespace=self.CONFIGMAP_NAMESPACE,
                    body=client.V1ConfigMap(
                        metadata=client.V1ObjectMeta(name=self.CONFIGMAP_NAME),
                        data={},
                    ),
                )
                logger.info("configmap_created", name=self.CONFIGMAP_NAME)

    @handle_k8s_errors
    def _load_session_from_k8s(self, session_id: str) -> Session | None:
        """从 K8s ConfigMap 加载会话"""
        if not self._k8s_available or not self._k8s_core_v1:
            return None

        cm = self._k8s_core_v1.read_namespaced_config_map(
            name=self.CONFIGMAP_NAME,
            namespace=self.CONFIGMAP_NAMESPACE,
        )

        session_data = cm.data.get(session_id) if cm.data else None
        if session_data:
            return Session.from_dict(json.loads(session_data))
        return None

    @handle_k8s_errors
    def _save_session_to_k8s(self, session: Session) -> bool:
        """保存会话到 K8s ConfigMap"""
        if not self._k8s_available or not self._k8s_core_v1:
            return False

        cm = self._k8s_core_v1.read_namespaced_config_map(
            name=self.CONFIGMAP_NAME,
            namespace=self.CONFIGMAP_NAMESPACE,
        )

        # 更新 data
        if cm.data is None:
            cm.data = {}
        cm.data[session.id] = json.dumps(session.to_dict())

        self._k8s_core_v1.patch_namespaced_config_map(
            name=self.CONFIGMAP_NAME,
            namespace=self.CONFIGMAP_NAMESPACE,
            body=cm,
        )
        return True

    @handle_k8s_errors
    def _delete_session_from_k8s(self, session_id: str) -> bool:
        """从 K8s ConfigMap 删除会话"""
        if not self._k8s_available or not self._k8s_core_v1:
            return False

        cm = self._k8s_core_v1.read_namespaced_config_map(
            name=self.CONFIGMAP_NAME,
            namespace=self.CONFIGMAP_NAMESPACE,
        )

        if cm.data and session_id in cm.data:
            del cm.data[session_id]
            self._k8s_core_v1.patch_namespaced_config_map(
                name=self.CONFIGMAP_NAME,
                namespace=self.CONFIGMAP_NAMESPACE,
                body=cm,
            )
        return True

    def create(self, user_id: str | None = None) -> Session:
        """创建新会话"""
        session = Session(
            user_id=user_id or "anonymous",
        )
        self._sessions[session.id] = session
        self._save_session_to_k8s(session)
        logger.info("session_created", session_id=session.id, user_id=user_id)
        return session

    def get(self, session_id: str) -> Session | None:
        """获取会话（优先内存，其次 K8s）"""
        # 先从内存获取
        if session_id in self._sessions:
            return self._sessions[session_id]

        # 尝试从 K8s 加载
        session = self._load_session_from_k8s(session_id)
        if session:
            self._sessions[session_id] = session
            return session

        return None

    def get_or_create(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> Session:
        """获取或创建会话"""
        if session_id:
            session = self.get(session_id)
            if session:
                return session

        return self.create(user_id)

    def save(self, session: Session) -> None:
        """保存会话"""
        self._sessions[session.id] = session
        self._save_session_to_k8s(session)
        logger.debug("session_saved", session_id=session.id)

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
        self._delete_session_from_k8s(session_id)
        logger.info("session_deleted", session_id=session_id)
        return True

    def list_sessions(self, user_id: str | None = None) -> list[Session]:
        """列出会话"""
        # TODO: 从 K8s 加载所有会话
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