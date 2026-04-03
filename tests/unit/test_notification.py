"""Notification Channels 单元测试"""

import pytest
from datetime import datetime

from app.infrastructure.notification import (
    NotificationChannelType,
    NotificationPriority,
    NotificationStatus,
    NotificationMessage,
    NotificationResult,
    NotificationChannelConfig,
    NotificationRouter,
    NotificationManager,
    SlackChannel,
    WebhookChannel,
    DingTalkChannel,
    FeishuChannel,
    EmailChannel,
    get_notification_router,
    get_notification_manager,
)


@pytest.fixture
def router():
    """创建通知路由器实例"""
    return NotificationRouter()


@pytest.fixture
def manager(router):
    """创建通知管理器实例"""
    return NotificationManager(router)


@pytest.fixture
def sample_message():
    """创建示例消息"""
    return NotificationMessage(
        title="Test Notification",
        content="This is a test notification",
        priority=NotificationPriority.HIGH,
        tags=["test", "sre"],
    )


class TestNotificationEnums:
    """枚举测试"""

    def test_channel_type_values(self):
        """测试渠道类型枚举"""
        assert NotificationChannelType.SLACK.value == "slack"
        assert NotificationChannelType.EMAIL.value == "email"
        assert NotificationChannelType.WEBHOOK.value == "webhook"
        assert NotificationChannelType.DINGTALK.value == "dingtalk"
        assert NotificationChannelType.FEISHU.value == "feishu"

    def test_priority_values(self):
        """测试优先级枚举"""
        assert NotificationPriority.CRITICAL.value == "critical"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.MEDIUM.value == "medium"
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.INFO.value == "info"


class TestNotificationMessage:
    """NotificationMessage 测试"""

    def test_message_creation(self):
        """测试消息创建"""
        message = NotificationMessage(
            title="Alert Title",
            content="Alert content",
            priority=NotificationPriority.CRITICAL,
            tags=["alert", "spark"],
            alert_id="alert-001",
        )

        assert message.title == "Alert Title"
        assert message.priority == NotificationPriority.CRITICAL
        assert "alert" in message.tags
        assert message.alert_id == "alert-001"

    def test_message_defaults(self):
        """测试消息默认值"""
        message = NotificationMessage(
            title="Test",
            content="Content",
        )

        assert message.priority == NotificationPriority.MEDIUM
        assert message.tags == []
        assert message.metadata == {}


class TestNotificationResult:
    """NotificationResult 测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = NotificationResult(
            success=True,
            channel_type=NotificationChannelType.SLACK,
            channel_name="slack-alerts",
        )

        assert result.success is True
        assert result.channel_type == NotificationChannelType.SLACK
        assert result.error is None

    def test_failure_result(self):
        """测试失败结果"""
        result = NotificationResult(
            success=False,
            channel_type=NotificationChannelType.EMAIL,
            channel_name="email-team",
            error="SMTP connection failed",
        )

        assert result.success is False
        assert result.error == "SMTP connection failed"


class TestNotificationChannelConfig:
    """NotificationChannelConfig 测试"""

    def test_config_creation(self):
        """测试配置创建"""
        config = NotificationChannelConfig(
            name="slack-alerts",
            type=NotificationChannelType.SLACK,
            config={"webhook_url": "https://hooks.slack.com/xxx"},
            priorities=[NotificationPriority.CRITICAL, NotificationPriority.HIGH],
        )

        assert config.name == "slack-alerts"
        assert config.type == NotificationChannelType.SLACK
        assert config.enabled is True
        assert NotificationPriority.CRITICAL in config.priorities

    def test_config_defaults(self):
        """测试配置默认值"""
        config = NotificationChannelConfig(
            name="test",
            type=NotificationChannelType.WEBHOOK,
        )

        assert config.enabled is True
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 30


class TestSlackChannel:
    """SlackChannel 测试"""

    def test_format_message(self):
        """测试消息格式化"""
        config = NotificationChannelConfig(
            name="slack-test",
            type=NotificationChannelType.SLACK,
            config={"webhook_url": "https://hooks.slack.com/test"},
        )
        channel = SlackChannel(config)

        message = NotificationMessage(
            title="Alert",
            content="Alert content",
            priority=NotificationPriority.HIGH,
            tags=["spark"],
        )

        formatted = channel.format_message(message)

        assert "attachments" in formatted
        assert formatted["attachments"][0]["title"] == "Alert"
        assert formatted["attachments"][0]["color"] == "#FFA500"  # HIGH priority

    def test_should_handle_priority(self):
        """测试优先级过滤"""
        config = NotificationChannelConfig(
            name="slack-critical",
            type=NotificationChannelType.SLACK,
            priorities=[NotificationPriority.CRITICAL],
        )
        channel = SlackChannel(config)

        critical_msg = NotificationMessage(
            title="Critical",
            content="content",
            priority=NotificationPriority.CRITICAL,
        )
        high_msg = NotificationMessage(
            title="High",
            content="content",
            priority=NotificationPriority.HIGH,
        )

        assert channel.should_handle(critical_msg) is True
        assert channel.should_handle(high_msg) is False

    def test_should_handle_tags(self):
        """测试标签过滤"""
        config = NotificationChannelConfig(
            name="slack-spark",
            type=NotificationChannelType.SLACK,
            tags=["spark"],
        )
        channel = SlackChannel(config)

        spark_msg = NotificationMessage(
            title="Spark Alert",
            content="content",
            tags=["spark", "data"],
        )
        k8s_msg = NotificationMessage(
            title="K8s Alert",
            content="content",
            tags=["kubernetes"],
        )

        assert channel.should_handle(spark_msg) is True
        assert channel.should_handle(k8s_msg) is False


class TestWebhookChannel:
    """WebhookChannel 测试"""

    def test_format_message(self):
        """测试消息格式化"""
        config = NotificationChannelConfig(
            name="webhook-test",
            type=NotificationChannelType.WEBHOOK,
            config={"url": "https://webhook.example.com/notify"},
        )
        channel = WebhookChannel(config)

        message = NotificationMessage(
            title="Alert",
            content="Alert content",
            priority=NotificationPriority.MEDIUM,
            tags=["test"],
            alert_id="alert-001",
        )

        formatted = channel.format_message(message)

        assert formatted["title"] == "Alert"
        assert formatted["content"] == "Alert content"
        assert formatted["priority"] == "medium"
        assert formatted["alert_id"] == "alert-001"


class TestDingTalkChannel:
    """DingTalkChannel 测试"""

    def test_format_message(self):
        """测试消息格式化"""
        config = NotificationChannelConfig(
            name="dingtalk-test",
            type=NotificationChannelType.DINGTALK,
        )
        channel = DingTalkChannel(config)

        message = NotificationMessage(
            title="告警",
            content="告警内容",
            priority=NotificationPriority.CRITICAL,
        )

        formatted = channel.format_message(message)

        assert formatted["msgtype"] == "markdown"
        assert "告警" in formatted["markdown"]["title"]


class TestFeishuChannel:
    """FeishuChannel 测试"""

    def test_format_message(self):
        """测试消息格式化"""
        config = NotificationChannelConfig(
            name="feishu-test",
            type=NotificationChannelType.FEISHU,
        )
        channel = FeishuChannel(config)

        message = NotificationMessage(
            title="通知",
            content="通知内容",
            priority=NotificationPriority.HIGH,
        )

        formatted = channel.format_message(message)

        assert formatted["msg_type"] == "post"
        assert "通知" in formatted["content"]["post"]["zh_cn"]["title"]


class TestEmailChannel:
    """EmailChannel 测试"""

    @pytest.mark.asyncio
    async def test_send_email(self):
        """测试发送邮件"""
        config = NotificationChannelConfig(
            name="email-test",
            type=NotificationChannelType.EMAIL,
            config={"recipients": ["admin@example.com"]},
        )
        channel = EmailChannel(config)

        message = NotificationMessage(
            title="Test Email",
            content="Email content",
            priority=NotificationPriority.MEDIUM,
        )

        result = await channel.send(message)

        assert result.success is True
        assert result.channel_type == NotificationChannelType.EMAIL


class TestNotificationRouter:
    """NotificationRouter 测试"""

    def test_register_channel(self, router):
        """测试注册渠道"""
        config = NotificationChannelConfig(
            name="slack-alerts",
            type=NotificationChannelType.SLACK,
        )

        router.register_channel(config)

        assert "slack-alerts" in router.list_channels()

    def test_unregister_channel(self, router):
        """测试注销渠道"""
        config = NotificationChannelConfig(
            name="test-channel",
            type=NotificationChannelType.WEBHOOK,
        )

        router.register_channel(config)
        assert "test-channel" in router.list_channels()

        result = router.unregister_channel("test-channel")
        assert result is True
        assert "test-channel" not in router.list_channels()

    def test_get_channel(self, router):
        """测试获取渠道"""
        config = NotificationChannelConfig(
            name="webhook-test",
            type=NotificationChannelType.WEBHOOK,
        )

        router.register_channel(config)
        channel = router.get_channel("webhook-test")

        assert channel is not None
        assert isinstance(channel, WebhookChannel)

    @pytest.mark.asyncio
    async def test_send_to_channel(self, router, sample_message):
        """测试发送到指定渠道"""
        config = NotificationChannelConfig(
            name="email-test",
            type=NotificationChannelType.EMAIL,
            config={"recipients": ["test@example.com"]},
        )

        router.register_channel(config)
        result = await router.send_to_channel("email-test", sample_message)

        assert result is not None
        assert result.success is True


class TestNotificationManager:
    """NotificationManager 测试"""

    def test_register_template(self, manager):
        """测试注册模板"""
        template = "Alert: {alert_name} - {message}"
        manager.register_template("alert_template", template)

        rendered = manager.render_template(
            "alert_template",
            {"alert_name": "HighCPU", "message": "CPU usage above 90%"},
        )

        assert "HighCPU" in rendered
        assert "CPU usage above 90%" in rendered

    def test_render_missing_template(self, manager):
        """测试渲染不存在的模板"""
        rendered = manager.render_template("nonexistent", {})
        assert rendered == ""

    @pytest.mark.asyncio
    async def test_send_alert_notification(self, manager, router):
        """测试发送告警通知"""
        config = NotificationChannelConfig(
            name="email-alerts",
            type=NotificationChannelType.EMAIL,
            config={"recipients": ["alerts@example.com"]},
            priorities=[NotificationPriority.CRITICAL, NotificationPriority.HIGH],
        )

        router.register_channel(config)

        alert = {
            "labels": {"alertname": "HighMemory", "severity": "critical"},
            "annotations": {"summary": "Memory usage is high"},
            "fingerprint": "abc123",
        }

        results = await manager.send_alert_notification(alert)

        assert len(results) > 0
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_send_patrol_notification(self, manager, router):
        """测试发送巡检通知"""
        config = NotificationChannelConfig(
            name="email-patrol",
            type=NotificationChannelType.EMAIL,
            config={"recipients": ["patrol@example.com"]},
        )

        router.register_channel(config)

        patrol_result = {
            "rule_name": "CheckMemory",
            "issues": [
                {"severity": "critical", "message": "Memory high"},
            ],
            "patrol_id": "patrol-001",
        }

        results = await manager.send_patrol_notification(patrol_result)

        assert len(results) > 0

    def test_severity_to_priority(self, manager):
        """测试严重级别转换"""
        assert manager._severity_to_priority("critical") == NotificationPriority.CRITICAL
        assert manager._severity_to_priority("warning") == NotificationPriority.MEDIUM
        assert manager._severity_to_priority("info") == NotificationPriority.INFO
        assert manager._severity_to_priority("unknown") == NotificationPriority.MEDIUM


class TestSingletonFunctions:
    """单例函数测试"""

    def test_get_notification_router_singleton(self):
        """测试获取路由器单例"""
        router1 = get_notification_router()
        router2 = get_notification_router()

        assert router1 is router2

    def test_get_notification_manager_singleton(self):
        """测试获取管理器单例"""
        manager1 = get_notification_manager()
        manager2 = get_notification_manager()

        assert manager1 is manager2