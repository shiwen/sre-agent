"""AlertManager 集成单元测试"""

import pytest
from datetime import datetime, timedelta

from app.infrastructure.alertmanager import (
    AlertState,
    AlertSeverity,
    SilenceState,
    AlertLabel,
    AlertAnnotation,
    Alert,
    AlertGroup,
    Silence,
    AlertManagerAlert,
    AlertManagerClient,
    AlertRule,
    AlertManager,
    SRE_ALERT_RULES,
    get_alertmanager_client,
    get_alertmanager,
)


@pytest.fixture
def client():
    """创建 AlertManager 客户端实例"""
    return AlertManagerClient(mock_mode=True)


@pytest.fixture
def manager(client):
    """创建 AlertManager 实例"""
    return AlertManager(client)


class TestAlertEnums:
    """枚举测试"""

    def test_alert_state_values(self):
        """测试告警状态枚举"""
        assert AlertState.FIRING.value == "firing"
        assert AlertState.PENDING.value == "pending"
        assert AlertState.RESOLVED.value == "resolved"
        assert AlertState.INACTIVE.value == "inactive"

    def test_alert_severity_values(self):
        """测试告警严重级别枚举"""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.INFO.value == "info"

    def test_silence_state_values(self):
        """测试静默状态枚举"""
        assert SilenceState.ACTIVE.value == "active"
        assert SilenceState.EXPIRED.value == "expired"


class TestAlertLabel:
    """AlertLabel 测试"""

    def test_label_creation(self):
        """测试标签创建"""
        label = AlertLabel(
            alertname="TestAlert",
            severity=AlertSeverity.WARNING,
            instance="localhost:9090",
        )

        assert label.alertname == "TestAlert"
        assert label.severity == AlertSeverity.WARNING
        assert label.instance == "localhost:9090"

    def test_label_to_dict(self):
        """测试标签转换为字典"""
        label = AlertLabel(
            alertname="TestAlert",
            severity=AlertSeverity.CRITICAL,
            custom_labels={"team": "platform"},
        )

        result = label.to_dict()

        assert result["alertname"] == "TestAlert"
        assert result["severity"] == "critical"
        assert result["team"] == "platform"


class TestAlertAnnotation:
    """AlertAnnotation 测试"""

    def test_annotation_creation(self):
        """测试注解创建"""
        annotation = AlertAnnotation(
            summary="Test alert summary",
            description="Test description",
            runbook_url="https://runbook.url",
        )

        assert annotation.summary == "Test alert summary"
        assert annotation.description == "Test description"

    def test_annotation_to_dict(self):
        """测试注解转换为字典"""
        annotation = AlertAnnotation(
            summary="Test summary",
            custom_annotations={"extra": "info"},
        )

        result = annotation.to_dict()

        assert result["summary"] == "Test summary"
        assert result["extra"] == "info"


class TestAlert:
    """Alert 测试"""

    def test_alert_creation(self):
        """测试告警创建"""
        alert = Alert(
            labels={"alertname": "TestAlert", "severity": "warning"},
            annotations={"summary": "Test summary"},
            state=AlertState.FIRING,
            source="sre-agent",
        )

        assert alert.labels["alertname"] == "TestAlert"
        assert alert.state == AlertState.FIRING
        assert alert.source == "sre-agent"


class TestSilence:
    """Silence 测试"""

    def test_silence_creation(self):
        """测试静默创建"""
        silence = Silence(
            id="silence-001",
            matchers=[{"name": "alertname", "value": "TestAlert"}],
            starts_at=datetime.now(),
            ends_at=datetime.now() + timedelta(hours=1),
            created_by="admin",
            comment="Test silence",
        )

        assert silence.id == "silence-001"
        assert silence.created_by == "admin"
        assert silence.status == SilenceState.ACTIVE


class TestAlertManagerClient:
    """AlertManagerClient 测试"""

    @pytest.mark.asyncio
    async def test_get_alerts(self, client):
        """测试获取告警"""
        alerts = await client.get_alerts()
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_get_silences(self, client):
        """测试获取静默"""
        silences = await client.get_silences()
        assert isinstance(silences, list)

    @pytest.mark.asyncio
    async def test_send_alerts(self, client):
        """测试发送告警"""
        alerts = [
            Alert(
                labels={"alertname": "TestAlert"},
                annotations={"summary": "Test"},
            )
        ]
        result = await client.send_alerts(alerts)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_silence(self, client):
        """测试创建静默"""
        silence_id = await client.create_silence(
            matchers={"alertname": "TestAlert"},
            duration_minutes=30,
            comment="Test",
        )
        assert silence_id is not None

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """测试健康检查"""
        is_healthy = await client.health_check()
        assert is_healthy is True


class TestAlertRule:
    """AlertRule 测试"""

    def test_rule_creation(self):
        """测试规则创建"""
        rule = AlertRule(
            name="TestRule",
            expr="up == 0",
            duration="5m",
            severity=AlertSeverity.CRITICAL,
            summary="Instance down",
        )

        assert rule.name == "TestRule"
        assert rule.expr == "up == 0"
        assert rule.severity == AlertSeverity.CRITICAL
        assert rule.enabled is True


class TestAlertManager:
    """AlertManager 测试"""

    def test_register_rule(self, manager):
        """测试注册规则"""
        rule = AlertRule(
            name="CustomRule",
            expr="custom_metric > 100",
            summary="Custom alert",
        )

        manager.register_rule(rule)

        assert manager.get_rule("CustomRule") is not None

    def test_get_all_rules(self, manager):
        """测试获取所有规则"""
        rules = manager.get_all_rules()
        assert len(rules) >= len(SRE_ALERT_RULES)

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, manager):
        """测试获取活跃告警"""
        alerts = await manager.get_active_alerts()
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_get_active_silences(self, manager):
        """测试获取活跃静默"""
        silences = await manager.get_active_silences()
        assert isinstance(silences, list)

    @pytest.mark.asyncio
    async def test_silence_alert(self, manager):
        """测试静默告警"""
        silence_id = await manager.silence_alert(
            matchers={"alertname": "TestAlert"},
            duration_minutes=60,
        )
        assert silence_id is not None

    @pytest.mark.asyncio
    async def test_create_alert_from_patrol_issue(self, manager):
        """测试从 Patrol 问题创建告警"""
        issue = {
            "message": "Memory usage high",
            "labels": {"instance": "node-1"},
        }

        alert = await manager.create_alert_from_patrol_issue(
            issue, "PatrolCheckFailed"
        )

        assert alert is not None
        assert alert.labels["alertname"] == "PatrolCheckFailed"
        assert "Memory usage high" in alert.annotations.get("issue_message", "")

    @pytest.mark.asyncio
    async def test_send_patrol_alerts(self, manager):
        """测试发送 Patrol 告警"""
        patrol_result = {
            "issues": [
                {"message": "Issue 1", "labels": {}},
                {"message": "Issue 2", "labels": {}},
            ]
        }

        count = await manager.send_patrol_alerts(patrol_result, "PatrolCheckFailed")
        assert count == 2

    @pytest.mark.asyncio
    async def test_generate_alert_report(self, manager):
        """测试生成告警报告"""
        report = await manager.generate_alert_report()

        assert "total_alerts" in report
        assert "total_silences" in report
        assert "by_severity" in report
        assert "by_name" in report


class TestSREAlertRules:
    """SRE 预定义规则测试"""

    def test_spark_rules_defined(self):
        """测试 Spark 规则定义"""
        rule_names = [r.name for r in SRE_ALERT_RULES]
        assert "SparkApplicationFailed" in rule_names
        assert "SparkHighFailedTasks" in rule_names

    def test_yunikorn_rules_defined(self):
        """测试 YuniKorn 规则定义"""
        rule_names = [r.name for r in SRE_ALERT_RULES]
        assert "YuniKornQueueMemoryHigh" in rule_names
        assert "YuniKornQueueCPUHigh" in rule_names

    def test_k8s_rules_defined(self):
        """测试 Kubernetes 规则定义"""
        rule_names = [r.name for r in SRE_ALERT_RULES]
        assert "K8sNodeNotReady" in rule_names
        assert "K8sHighNodeCPU" in rule_names
        assert "K8sHighNodeMemory" in rule_names

    def test_patrol_rules_defined(self):
        """测试 Patrol 规则定义"""
        rule_names = [r.name for r in SRE_ALERT_RULES]
        assert "PatrolCheckFailed" in rule_names
        assert "PatrolHighIssueCount" in rule_names

    def test_all_rules_have_required_fields(self):
        """测试所有规则都有必需字段"""
        for rule in SRE_ALERT_RULES:
            assert rule.name, f"Rule missing name"
            assert rule.expr, f"Rule {rule.name} missing expr"
            assert rule.summary, f"Rule {rule.name} missing summary"
            assert rule.severity, f"Rule {rule.name} missing severity"


class TestSingletonFunctions:
    """单例函数测试"""

    def test_get_alertmanager_client_singleton(self):
        """测试获取客户端单例"""
        client1 = get_alertmanager_client()
        client2 = get_alertmanager_client()

        assert client1 is client2

    def test_get_alertmanager_singleton(self):
        """测试获取管理器单例"""
        manager1 = get_alertmanager()
        manager2 = get_alertmanager()

        assert manager1 is manager2