"""通知渠道模块

支持多种通知渠道发送告警和巡检报告。
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class NotificationChannelType(str, Enum):
    """通知渠道类型"""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DINGTALK = "dingtalk"
    WECOM = "wecom"
    FEISHU = "feishu"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"


class NotificationPriority(str, Enum):
    """通知优先级"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class NotificationStatus(str, Enum):
    """通知状态"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class NotificationMessage(BaseModel):
    """通知消息"""

    title: str
    content: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None

    # 关联信息
    alert_id: str | None = None
    patrol_id: str | None = None
    correlation_id: str | None = None


class NotificationResult(BaseModel):
    """通知结果"""

    success: bool
    channel_type: NotificationChannelType
    channel_name: str
    message_id: str | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0


class NotificationChannelConfig(BaseModel):
    """通知渠道配置"""

    name: str
    type: NotificationChannelType
    enabled: bool = True

    # 渠道特定配置
    config: dict[str, Any] = Field(default_factory=dict)

    # 路由规则
    priorities: list[NotificationPriority] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)  # 匹配的标签

    # 重试配置
    max_retries: int = 3
    retry_delay_seconds: int = 30


class NotificationChannel(ABC):
    """通知渠道基类"""

    def __init__(self, config: NotificationChannelConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    @abstractmethod
    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送通知"""
        pass

    @abstractmethod
    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化消息"""
        pass

    def should_handle(self, message: NotificationMessage) -> bool:
        """判断是否应该处理此消息"""
        if not self.config.enabled:
            return False

        # 检查优先级
        if self.config.priorities and message.priority not in self.config.priorities:
            return False

        # 检查标签
        if self.config.tags:
            if not any(tag in message.tags for tag in self.config.tags):
                return False

        return True

    async def _init_client(self) -> None:
        """初始化 HTTP 客户端"""
        if self._client is None and HTTPX_AVAILABLE:
            self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


class SlackChannel(NotificationChannel):
    """Slack 通知渠道"""

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送 Slack 消息"""
        webhook_url = self.config.config.get("webhook_url")
        if not webhook_url:
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.SLACK,
                channel_name=self.config.name,
                error="Slack webhook URL not configured",
            )

        await self._init_client()

        payload = self.format_message(message)

        try:
            response = await self._client.post(webhook_url, json=payload)
            response.raise_for_status()

            logger.info("slack_notification_sent", channel=self.config.name)
            return NotificationResult(
                success=True,
                channel_type=NotificationChannelType.SLACK,
                channel_name=self.config.name,
            )

        except Exception as e:
            logger.error("slack_notification_failed", error=str(e))
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.SLACK,
                channel_name=self.config.name,
                error=str(e),
            )

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化 Slack 消息"""
        # 颜色映射
        color_map = {
            NotificationPriority.CRITICAL: "#FF0000",
            NotificationPriority.HIGH: "#FFA500",
            NotificationPriority.MEDIUM: "#FFFF00",
            NotificationPriority.LOW: "#00FF00",
            NotificationPriority.INFO: "#808080",
        }

        attachment = {
            "color": color_map.get(message.priority, "#808080"),
            "title": message.title,
            "text": message.content,
            "footer": f"SRE Agent | {message.priority.value.upper()}",
            "ts": int(datetime.now().timestamp()),
        }

        if message.tags:
            attachment["fields"] = [
                {"title": "Tags", "value": ", ".join(message.tags), "short": True}
            ]

        return {
            "attachments": [attachment],
            "username": self.config.config.get("username", "SRE Agent"),
            "icon_emoji": self.config.config.get("icon_emoji", ":robot_face:"),
        }


class WebhookChannel(NotificationChannel):
    """通用 Webhook 通知渠道"""

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送 Webhook 请求"""
        url = self.config.config.get("url")
        if not url:
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.WEBHOOK,
                channel_name=self.config.name,
                error="Webhook URL not configured",
            )

        await self._init_client()

        payload = self.format_message(message)
        headers = self.config.config.get("headers", {})

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            logger.info("webhook_notification_sent", channel=self.config.name)
            return NotificationResult(
                success=True,
                channel_type=NotificationChannelType.WEBHOOK,
                channel_name=self.config.name,
            )

        except Exception as e:
            logger.error("webhook_notification_failed", error=str(e))
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.WEBHOOK,
                channel_name=self.config.name,
                error=str(e),
            )

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化 Webhook 消息"""
        return {
            "title": message.title,
            "content": message.content,
            "priority": message.priority.value,
            "tags": message.tags,
            "metadata": message.metadata,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None,
            "alert_id": message.alert_id,
            "patrol_id": message.patrol_id,
        }


class DingTalkChannel(NotificationChannel):
    """钉钉通知渠道"""

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送钉钉消息"""
        webhook_url = self.config.config.get("webhook_url")
        if not webhook_url:
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.DINGTALK,
                channel_name=self.config.name,
                error="DingTalk webhook URL not configured",
            )

        await self._init_client()

        payload = self.format_message(message)

        try:
            response = await self._client.post(webhook_url, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("errcode", 0) != 0:
                return NotificationResult(
                    success=False,
                    channel_type=NotificationChannelType.DINGTALK,
                    channel_name=self.config.name,
                    error=result.get("errmsg", "Unknown error"),
                )

            logger.info("dingtalk_notification_sent", channel=self.config.name)
            return NotificationResult(
                success=True,
                channel_type=NotificationChannelType.DINGTALK,
                channel_name=self.config.name,
            )

        except Exception as e:
            logger.error("dingtalk_notification_failed", error=str(e))
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.DINGTALK,
                channel_name=self.config.name,
                error=str(e),
            )

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化钉钉消息"""
        # 钉钉 Markdown 格式
        text = f"### {message.title}\n\n{message.content}"

        if message.tags:
            text += f"\n\n**标签**: {', '.join(message.tags)}"

        text += f"\n\n**优先级**: {message.priority.value.upper()}"
        text += f"\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return {
            "msgtype": "markdown",
            "markdown": {
                "title": message.title,
                "text": text,
            },
        }


class FeishuChannel(NotificationChannel):
    """飞书通知渠道"""

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送飞书消息"""
        webhook_url = self.config.config.get("webhook_url")
        if not webhook_url:
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.FEISHU,
                channel_name=self.config.name,
                error="Feishu webhook URL not configured",
            )

        await self._init_client()

        payload = self.format_message(message)

        try:
            response = await self._client.post(webhook_url, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("code", 0) != 0:
                return NotificationResult(
                    success=False,
                    channel_type=NotificationChannelType.FEISHU,
                    channel_name=self.config.name,
                    error=result.get("msg", "Unknown error"),
                )

            logger.info("feishu_notification_sent", channel=self.config.name)
            return NotificationResult(
                success=True,
                channel_type=NotificationChannelType.FEISHU,
                channel_name=self.config.name,
            )

        except Exception as e:
            logger.error("feishu_notification_failed", error=str(e))
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.FEISHU,
                channel_name=self.config.name,
                error=str(e),
            )

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化飞书消息"""
        # 飞书富文本格式
        content = []
        content.append([{"tag": "text", "text": message.content}])

        if message.tags:
            content.append([
                {"tag": "text", "text": f"标签: {', '.join(message.tags)}"}
            ])

        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": message.title,
                        "content": content,
                    }
                }
            },
        }


class EmailChannel(NotificationChannel):
    """邮件通知渠道（模拟）"""

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送邮件"""
        # 邮件发送需要 SMTP 配置，这里模拟发送
        recipients = self.config.config.get("recipients", [])
        if not recipients:
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.EMAIL,
                channel_name=self.config.name,
                error="No email recipients configured",
            )

        # 模拟发送
        logger.info(
            "email_notification_sent",
            channel=self.config.name,
            recipients=recipients,
            subject=message.title,
        )

        return NotificationResult(
            success=True,
            channel_type=NotificationChannelType.EMAIL,
            channel_name=self.config.name,
        )

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化邮件消息"""
        body = f"""
{message.content}

Priority: {message.priority.value.upper()}
Tags: {', '.join(message.tags) if message.tags else 'None'}
Timestamp: {message.timestamp or datetime.now()}
Alert ID: {message.alert_id or 'N/A'}
Patrol ID: {message.patrol_id or 'N/A'}

---
Sent by SRE Agent
"""
        return {
            "subject": message.title,
            "body": body,
            "recipients": self.config.config.get("recipients", []),
        }


class NotificationRouter:
    """通知路由器

    根据消息优先级和标签路由到合适的渠道。
    """

    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    def register_channel(self, config: NotificationChannelConfig) -> None:
        """注册通知渠道"""
        channel = self._create_channel(config)
        self._channels[config.name] = channel
        logger.info("notification_channel_registered", name=config.name, type=config.type.value)

    def _create_channel(self, config: NotificationChannelConfig) -> NotificationChannel:
        """创建渠道实例"""
        channel_map = {
            NotificationChannelType.SLACK: SlackChannel,
            NotificationChannelType.WEBHOOK: WebhookChannel,
            NotificationChannelType.DINGTALK: DingTalkChannel,
            NotificationChannelType.FEISHU: FeishuChannel,
            NotificationChannelType.EMAIL: EmailChannel,
        }

        channel_class = channel_map.get(config.type)
        if channel_class is None:
            logger.warning("unknown_channel_type", type=config.type.value)
            return WebhookChannel(config)  # 默认使用 Webhook

        return channel_class(config)

    def unregister_channel(self, name: str) -> bool:
        """注销渠道"""
        if name in self._channels:
            channel = self._channels.pop(name)
            # 异步关闭需要在外部处理
            logger.info("notification_channel_unregistered", name=name)
            return True
        return False

    def get_channel(self, name: str) -> NotificationChannel | None:
        """获取渠道"""
        return self._channels.get(name)

    def list_channels(self) -> list[str]:
        """列出所有渠道"""
        return list(self._channels.keys())

    async def route(self, message: NotificationMessage) -> list[NotificationResult]:
        """路由消息到合适的渠道"""
        results = []

        for name, channel in self._channels.items():
            if channel.should_handle(message):
                result = await channel.send(message)
                results.append(result)

        if not results:
            logger.warning("no_channels_matched", message_title=message.title)

        return results

    async def send_to_channel(
        self,
        channel_name: str,
        message: NotificationMessage,
    ) -> NotificationResult | None:
        """发送到指定渠道"""
        channel = self._channels.get(channel_name)
        if channel is None:
            logger.warning("channel_not_found", name=channel_name)
            return NotificationResult(
                success=False,
                channel_type=NotificationChannelType.WEBHOOK,
                channel_name=channel_name,
                error="Channel not found",
            )

        return await channel.send(message)

    async def broadcast(self, message: NotificationMessage) -> list[NotificationResult]:
        """广播到所有启用的渠道"""
        results = []

        for name, channel in self._channels.items():
            if channel.config.enabled:
                result = await channel.send(message)
                results.append(result)

        return results

    async def close_all(self) -> None:
        """关闭所有渠道"""
        for channel in self._channels.values():
            await channel.close()


class NotificationManager:
    """通知管理器

    提供高级通知功能，包括模板、批量发送等。
    """

    def __init__(self, router: NotificationRouter | None = None) -> None:
        self._router = router or NotificationRouter()
        self._templates: dict[str, str] = {}

    def register_template(self, name: str, template: str) -> None:
        """注册消息模板"""
        self._templates[name] = template

    def render_template(
        self,
        name: str,
        variables: dict[str, Any],
    ) -> str:
        """渲染模板"""
        template = self._templates.get(name)
        if template is None:
            return ""

        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning("template_render_failed", missing_key=str(e))
            return template

    async def send_alert_notification(
        self,
        alert: dict[str, Any],
        channels: list[str] | None = None,
    ) -> list[NotificationResult]:
        """发送告警通知"""
        message = NotificationMessage(
            title=f"Alert: {alert.get('labels', {}).get('alertname', 'Unknown')}",
            content=alert.get("annotations", {}).get("summary", "No summary"),
            priority=self._severity_to_priority(
                alert.get("labels", {}).get("severity", "warning")
            ),
            tags=["alert", alert.get("labels", {}).get("component", "")],
            alert_id=alert.get("fingerprint"),
        )

        if channels:
            results = []
            for channel_name in channels:
                result = await self._router.send_to_channel(channel_name, message)
                if result:
                    results.append(result)
            return results

        return await self._router.route(message)

    async def send_patrol_notification(
        self,
        patrol_result: dict[str, Any],
        channels: list[str] | None = None,
    ) -> list[NotificationResult]:
        """发送巡检通知"""
        issues = patrol_result.get("issues", [])
        severity = "critical" if any(i.get("severity") == "critical" for i in issues) else "warning"

        message = NotificationMessage(
            title=f"Patrol Report: {patrol_result.get('rule_name', 'Unknown')}",
            content=f"Found {len(issues)} issues during patrol check",
            priority=self._severity_to_priority(severity),
            tags=["patrol", patrol_result.get("rule_name", "")],
            patrol_id=patrol_result.get("patrol_id"),
        )

        if channels:
            results = []
            for channel_name in channels:
                result = await self._router.send_to_channel(channel_name, message)
                if result:
                    results.append(result)
            return results

        return await self._router.route(message)

    def _severity_to_priority(self, severity: str) -> NotificationPriority:
        """转换严重级别到优先级"""
        severity_map = {
            "critical": NotificationPriority.CRITICAL,
            "high": NotificationPriority.HIGH,
            "warning": NotificationPriority.MEDIUM,
            "info": NotificationPriority.INFO,
            "none": NotificationPriority.LOW,
        }
        return severity_map.get(severity.lower(), NotificationPriority.MEDIUM)

    def get_router(self) -> NotificationRouter:
        """获取路由器"""
        return self._router


# 全局实例
_notification_router: NotificationRouter | None = None
_notification_manager: NotificationManager | None = None


def get_notification_router() -> NotificationRouter:
    """获取全局通知路由器"""
    global _notification_router
    if _notification_router is None:
        _notification_router = NotificationRouter()
    return _notification_router


def get_notification_manager() -> NotificationManager:
    """获取全局通知管理器"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(get_notification_router())
    return _notification_manager