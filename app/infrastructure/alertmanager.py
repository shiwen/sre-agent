"""Alert Manager 集成

与 Prometheus Alertmanager 交互，管理告警和静默。
"""

import json
from datetime import datetime, timedelta
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
    logger.warning("httpx_not_available", note="Using mock data")


class AlertState(str, Enum):
    """告警状态"""

    FIRING = "firing"
    PENDING = "pending"
    RESOLVED = "resolved"
    INACTIVE = "inactive"


class AlertSeverity(str, Enum):
    """告警严重级别"""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


class SilenceState(str, Enum):
    """静默状态"""

    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"


class AlertLabel(BaseModel):
    """告警标签"""

    alertname: str
    severity: AlertSeverity = AlertSeverity.WARNING
    instance: str | None = None
    job: str | None = None
    namespace: str | None = None
    custom_labels: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """转换为字典"""
        result = {"alertname": self.alertname, "severity": self.severity.value}
        if self.instance:
            result["instance"] = self.instance
        if self.job:
            result["job"] = self.job
        if self.namespace:
            result["namespace"] = self.namespace
        result.update(self.custom_labels)
        return result


class AlertAnnotation(BaseModel):
    """告警注解"""

    summary: str
    description: str | None = None
    runbook_url: str | None = None
    custom_annotations: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """转换为字典"""
        result = {"summary": self.summary}
        if self.description:
            result["description"] = self.description
        if self.runbook_url:
            result["runbook_url"] = self.runbook_url
        result.update(self.custom_annotations)
        return result


class Alert(BaseModel):
    """告警信息"""

    labels: dict[str, str]
    annotations: dict[str, str] = Field(default_factory=dict)
    state: AlertState = AlertState.FIRING
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    generator_url: str | None = None
    fingerprint: str | None = None

    # SRE Agent 扩展字段
    source: str = "sre-agent"
    rule_id: str | None = None
    app_id: str | None = None
    correlation_id: str | None = None


class AlertGroup(BaseModel):
    """告警组"""

    labels: dict[str, str] = Field(default_factory=dict)
    receiver: str | None = None
    alerts: list[Alert] = Field(default_factory=list)


class Silence(BaseModel):
    """静默规则"""

    id: str | None = None
    matchers: list[dict[str, Any]] = Field(default_factory=list)
    starts_at: datetime
    ends_at: datetime
    created_by: str
    comment: str
    status: SilenceState = SilenceState.ACTIVE


class AlertManagerAlert(BaseModel):
    """Alertmanager 告警格式"""

    status: AlertState
    labels: dict[str, str]
    annotations: dict[str, str] = Field(default_factory=dict)
    starts_at: datetime
    ends_at: datetime | None = None
    generator_url: str | None = None
    fingerprint: str | None = None
    receivers: list[str] = Field(default_factory=list)


class AlertManagerClient:
    """Alertmanager API 客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:9093",
        timeout_seconds: float = 30.0,
        mock_mode: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._mock_mode = mock_mode
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    def _init_client(self) -> None:
        """初始化 HTTP 客户端"""
        if self._initialized:
            return

        if not HTTPX_AVAILABLE or self._mock_mode:
            logger.warning("alertmanager_client_unavailable", fallback="mock_mode")
            self._initialized = True
            return

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )
        self._initialized = True

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def is_available(self) -> bool:
        """检查客户端是否可用"""
        self._init_client()
        return self._client is not None

    # ============ 告警操作 ============

    async def get_alerts(
        self,
        active: bool = True,
        silenced: bool = False,
        inhibited: bool = False,
        unprocessed: bool = False,
        filter_labels: dict[str, str] | None = None,
    ) -> list[AlertManagerAlert]:
        """获取告警列表"""
        self._init_client()

        if not self.is_available:
            return self._mock_alerts()

        params: dict[str, Any] = {
            "active": str(active).lower(),
            "silenced": str(silenced).lower(),
            "inhibited": str(inhibited).lower(),
            "unprocessed": str(unprocessed).lower(),
        }

        if filter_labels:
            for key, value in filter_labels.items():
                params["filter"] = params.get("filter", "") + f'{key}="{value}",'

        try:
            response = await self._client.get("/api/v2/alerts", params=params)
            response.raise_for_status()
            data = response.json()

            alerts = []
            for item in data:
                try:
                    alert = self._parse_alert(item)
                    alerts.append(alert)
                except Exception as e:
                    logger.warning("parse_alert_failed", error=str(e))

            return alerts

        except Exception as e:
            logger.error("get_alerts_failed", error=str(e))
            return self._mock_alerts()

    async def get_alert(self, fingerprint: str) -> AlertManagerAlert | None:
        """获取单个告警"""
        self._init_client()

        if not self.is_available:
            return self._mock_alert(fingerprint)

        try:
            response = await self._client.get(f"/api/v2/alerts/{fingerprint}")
            response.raise_for_status()
            data = response.json()
            return self._parse_alert(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("get_alert_failed", fingerprint=fingerprint, error=str(e))
            return None
        except Exception as e:
            logger.error("get_alert_failed", fingerprint=fingerprint, error=str(e))
            return None

    async def send_alerts(self, alerts: list[Alert]) -> bool:
        """发送告警到 Alertmanager"""
        self._init_client()

        if not self.is_available:
            logger.info("mock_send_alerts", count=len(alerts))
            return True

        payload = []
        for alert in alerts:
            item = {
                "labels": alert.labels,
                "annotations": alert.annotations,
                "startsAt": (alert.starts_at or datetime.now()).isoformat(),
            }
            if alert.ends_at:
                item["endsAt"] = alert.ends_at.isoformat()
            if alert.generator_url:
                item["generatorURL"] = alert.generator_url
            payload.append(item)

        try:
            response = await self._client.post(
                "/api/v2/alerts",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info("send_alerts_success", count=len(alerts))
            return True

        except Exception as e:
            logger.error("send_alerts_failed", error=str(e))
            return False

    async def resolve_alerts(self, fingerprints: list[str]) -> bool:
        """解决告警"""
        self._init_client()

        if not self.is_available:
            logger.info("mock_resolve_alerts", fingerprints=fingerprints)
            return True

        payload = [
            {
                "fingerprint": fp,
                "endsAt": datetime.now().isoformat(),
            }
            for fp in fingerprints
        ]

        try:
            response = await self._client.post(
                "/api/v2/alerts",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info("resolve_alerts_success", count=len(fingerprints))
            return True

        except Exception as e:
            logger.error("resolve_alerts_failed", error=str(e))
            return False

    # ============ 静默操作 ============

    async def get_silences(
        self,
        filter_labels: dict[str, str] | None = None,
    ) -> list[Silence]:
        """获取静默列表"""
        self._init_client()

        if not self.is_available:
            return self._mock_silences()

        params = {}
        if filter_labels:
            filter_str = ",".join(f'{k}="{v}"' for k, v in filter_labels.items())
            params["filter"] = filter_str

        try:
            response = await self._client.get("/api/v2/silences", params=params)
            response.raise_for_status()
            data = response.json()

            silences = []
            for item in data:
                try:
                    silence = self._parse_silence(item)
                    silences.append(silence)
                except Exception as e:
                    logger.warning("parse_silence_failed", error=str(e))

            return silences

        except Exception as e:
            logger.error("get_silences_failed", error=str(e))
            return self._mock_silences()

    async def get_silence(self, silence_id: str) -> Silence | None:
        """获取单个静默"""
        self._init_client()

        if not self.is_available:
            return self._mock_silence(silence_id)

        try:
            response = await self._client.get(f"/api/v2/silence/{silence_id}")
            response.raise_for_status()
            data = response.json()
            return self._parse_silence(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("get_silence_failed", silence_id=silence_id, error=str(e))
            return None
        except Exception as e:
            logger.error("get_silence_failed", silence_id=silence_id, error=str(e))
            return None

    async def create_silence(
        self,
        matchers: dict[str, str],
        duration_minutes: int = 60,
        created_by: str = "sre-agent",
        comment: str = "Silenced by SRE Agent",
    ) -> str | None:
        """创建静默"""
        self._init_client()

        if not self.is_available:
            logger.info("mock_create_silence", matchers=matchers)
            return "mock-silence-id"

        starts_at = datetime.now()
        ends_at = starts_at + timedelta(minutes=duration_minutes)

        matcher_list = [
            {"name": k, "value": v, "isRegex": False}
            for k, v in matchers.items()
        ]

        payload = {
            "matchers": matcher_list,
            "startsAt": starts_at.isoformat(),
            "endsAt": ends_at.isoformat(),
            "createdBy": created_by,
            "comment": comment,
        }

        try:
            response = await self._client.post(
                "/api/v2/silences",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            silence_id = data.get("silenceID")
            logger.info("create_silence_success", silence_id=silence_id)
            return silence_id

        except Exception as e:
            logger.error("create_silence_failed", error=str(e))
            return None

    async def delete_silence(self, silence_id: str) -> bool:
        """删除静默"""
        self._init_client()

        if not self.is_available:
            logger.info("mock_delete_silence", silence_id=silence_id)
            return True

        try:
            response = await self._client.delete(f"/api/v2/silence/{silence_id}")
            response.raise_for_status()
            logger.info("delete_silence_success", silence_id=silence_id)
            return True

        except Exception as e:
            logger.error("delete_silence_failed", silence_id=silence_id, error=str(e))
            return False

    # ============ 状态检查 ============

    async def get_status(self) -> dict[str, Any]:
        """获取 Alertmanager 状态"""
        self._init_client()

        if not self.is_available:
            return {"status": "mock", "available": False}

        try:
            response = await self._client.get("/api/v2/status")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("get_status_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    async def health_check(self) -> bool:
        """健康检查"""
        self._init_client()

        if not self.is_available:
            return True  # Mock mode

        try:
            response = await self._client.get("/-/healthy")
            return response.status_code == 200
        except Exception:
            return False

    # ============ 解析方法 ============

    def _parse_alert(self, data: dict[str, Any]) -> AlertManagerAlert:
        """解析告警数据"""
        return AlertManagerAlert(
            status=AlertState(data.get("status", {}).get("state", "firing")),
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            starts_at=self._parse_timestamp(data.get("startsAt")),
            ends_at=self._parse_timestamp(data.get("endsAt")),
            generator_url=data.get("generatorURL"),
            fingerprint=data.get("fingerprint"),
            receivers=data.get("receivers", []),
        )

    def _parse_silence(self, data: dict[str, Any]) -> Silence:
        """解析静默数据"""
        status = SilenceState.ACTIVE
        if data.get("status", {}).get("state") == "expired":
            status = SilenceState.EXPIRED
        elif data.get("status", {}).get("state") == "pending":
            status = SilenceState.PENDING

        return Silence(
            id=data.get("id"),
            matchers=data.get("matchers", []),
            starts_at=self._parse_timestamp(data.get("startsAt")),
            ends_at=self._parse_timestamp(data.get("endsAt")),
            created_by=data.get("createdBy", "unknown"),
            comment=data.get("comment", ""),
            status=status,
        )

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """解析时间戳"""
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    # ============ Mock 数据 ============

    def _mock_alerts(self) -> list[AlertManagerAlert]:
        """Mock 告警列表"""
        return [
            AlertManagerAlert(
                status=AlertState.FIRING,
                labels={"alertname": "HighMemoryUsage", "severity": "warning"},
                annotations={"summary": "Memory usage above 80%"},
                starts_at=datetime.now() - timedelta(minutes=10),
                fingerprint="abc123",
                receivers=["default"],
            ),
            AlertManagerAlert(
                status=AlertState.FIRING,
                labels={"alertname": "SparkAppFailed", "severity": "critical"},
                annotations={"summary": "Spark application failed"},
                starts_at=datetime.now() - timedelta(minutes=5),
                fingerprint="def456",
                receivers=["default"],
            ),
        ]

    def _mock_alert(self, fingerprint: str) -> AlertManagerAlert:
        """Mock 单个告警"""
        return AlertManagerAlert(
            status=AlertState.FIRING,
            labels={"alertname": "MockAlert"},
            annotations={"summary": "Mock alert"},
            starts_at=datetime.now(),
            fingerprint=fingerprint,
        )

    def _mock_silences(self) -> list[Silence]:
        """Mock 静默列表"""
        return [
            Silence(
                id="silence-001",
                matchers=[{"name": "alertname", "value": "TestAlert", "isRegex": False}],
                starts_at=datetime.now() - timedelta(minutes=30),
                ends_at=datetime.now() + timedelta(minutes=30),
                created_by="admin",
                comment="Testing silence",
            ),
        ]

    def _mock_silence(self, silence_id: str) -> Silence:
        """Mock 单个静默"""
        return Silence(
            id=silence_id,
            matchers=[],
            starts_at=datetime.now(),
            ends_at=datetime.now() + timedelta(hours=1),
            created_by="sre-agent",
            comment="Mock silence",
        )


class AlertRule(BaseModel):
    """告警规则定义"""

    name: str
    expr: str  # PromQL expression
    duration: str = "5m"  # for how long before alert fires
    severity: AlertSeverity = AlertSeverity.WARNING
    summary: str
    description: str | None = None
    runbook_url: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


# SRE Agent 预定义告警规则
SRE_ALERT_RULES = [
    AlertRule(
        name="SparkApplicationFailed",
        expr='sre_spark_applications_total{status="FAILED"} > 0',
        duration="1m",
        severity=AlertSeverity.CRITICAL,
        summary="Spark application failed",
        description="A Spark application has failed and requires attention",
        labels={"component": "spark", "team": "data-platform"},
    ),
    AlertRule(
        name="SparkHighFailedTasks",
        expr="sre_spark_application_failed_tasks > 10",
        duration="5m",
        severity=AlertSeverity.WARNING,
        summary="High number of failed tasks in Spark application",
        labels={"component": "spark", "team": "data-platform"},
    ),
    AlertRule(
        name="YuniKornQueueMemoryHigh",
        expr="sre_yunikorn_queue_memory_used_bytes / sre_yunikorn_queue_memory_allocated_bytes > 0.9",
        duration="5m",
        severity=AlertSeverity.WARNING,
        summary="YuniKorn queue memory usage above 90%",
        labels={"component": "yunikorn", "team": "platform"},
    ),
    AlertRule(
        name="YuniKornQueueCPUHigh",
        expr="sre_yunikorn_queue_cpu_used_cores / sre_yunikorn_queue_cpu_allocated_cores > 0.9",
        duration="5m",
        severity=AlertSeverity.WARNING,
        summary="YuniKorn queue CPU usage above 90%",
        labels={"component": "yunikorn", "team": "platform"},
    ),
    AlertRule(
        name="K8sNodeNotReady",
        expr='sre_k8s_nodes_total{status="not_ready"} > 0',
        duration="2m",
        severity=AlertSeverity.CRITICAL,
        summary="Kubernetes node is not ready",
        labels={"component": "kubernetes", "team": "platform"},
    ),
    AlertRule(
        name="K8sHighNodeCPU",
        expr="sre_k8s_node_cpu_usage_percent > 80",
        duration="10m",
        severity=AlertSeverity.WARNING,
        summary="Kubernetes node CPU usage above 80%",
        labels={"component": "kubernetes", "team": "platform"},
    ),
    AlertRule(
        name="K8sHighNodeMemory",
        expr="sre_k8s_node_memory_usage_percent > 85",
        duration="10m",
        severity=AlertSeverity.WARNING,
        summary="Kubernetes node memory usage above 85%",
        labels={"component": "kubernetes", "team": "platform"},
    ),
    AlertRule(
        name="PatrolCheckFailed",
        expr='sre_patrol_total{status="failed"} > 0',
        duration="1m",
        severity=AlertSeverity.WARNING,
        summary="Patrol check failed",
        labels={"component": "sre-agent", "team": "sre"},
    ),
    AlertRule(
        name="PatrolHighIssueCount",
        expr="sum by (rule_name) (sre_patrol_issues_found) > 5",
        duration="5m",
        severity=AlertSeverity.WARNING,
        summary="High number of issues found by patrol",
        labels={"component": "sre-agent", "team": "sre"},
    ),
    AlertRule(
        name="AgentHighToolErrors",
        expr='sum by (tool_name) (sre_agent_tool_calls_total{status="error"}) > 10',
        duration="10m",
        severity=AlertSeverity.WARNING,
        summary="High error rate for SRE Agent tool calls",
        labels={"component": "sre-agent", "team": "sre"},
    ),
]


class AlertManager:
    """告警管理器

    整合告警规则、告警发送和静默管理。
    """

    def __init__(self, client: AlertManagerClient | None = None) -> None:
        self._client = client or get_alertmanager_client()
        self._rules = {rule.name: rule for rule in SRE_ALERT_RULES}

    def register_rule(self, rule: AlertRule) -> None:
        """注册告警规则"""
        self._rules[rule.name] = rule
        logger.info("alert_rule_registered", name=rule.name)

    def get_rule(self, name: str) -> AlertRule | None:
        """获取告警规则"""
        return self._rules.get(name)

    def get_all_rules(self) -> list[AlertRule]:
        """获取所有规则"""
        return list(self._rules.values())

    async def create_alert_from_patrol_issue(
        self,
        issue: dict[str, Any],
        rule_name: str,
    ) -> Alert | None:
        """从 Patrol 问题创建告警"""
        rule = self._rules.get(rule_name)
        if not rule:
            logger.warning("rule_not_found", rule_name=rule_name)
            return None

        labels = {
            "alertname": rule.name,
            "severity": rule.severity.value,
        }
        labels.update(rule.labels)
        labels.update(issue.get("labels", {}))

        annotations = {
            "summary": rule.summary,
        }
        if rule.description:
            annotations["description"] = rule.description
        if issue.get("message"):
            annotations["issue_message"] = issue["message"]
        if rule.runbook_url:
            annotations["runbook_url"] = rule.runbook_url

        return Alert(
            labels=labels,
            annotations=annotations,
            state=AlertState.FIRING,
            starts_at=datetime.now(),
            source="sre-agent",
            rule_id=rule_name,
            app_id=issue.get("app_id"),
            correlation_id=issue.get("correlation_id"),
        )

    async def send_patrol_alerts(
        self,
        patrol_result: dict[str, Any],
        rule_name: str,
    ) -> int:
        """发送 Patrol 告警"""
        issues = patrol_result.get("issues", [])
        if not issues:
            return 0

        alerts = []
        for issue in issues:
            alert = await self.create_alert_from_patrol_issue(issue, rule_name)
            if alert:
                alerts.append(alert)

        if alerts:
            success = await self._client.send_alerts(alerts)
            return len(alerts) if success else 0

        return 0

    async def silence_alert(
        self,
        matchers: dict[str, str],
        duration_minutes: int = 60,
        comment: str = "Silenced by SRE Agent",
    ) -> str | None:
        """静默告警"""
        return await self._client.create_silence(
            matchers=matchers,
            duration_minutes=duration_minutes,
            comment=comment,
        )

    async def get_active_alerts(self) -> list[AlertManagerAlert]:
        """获取活跃告警"""
        return await self._client.get_alerts(active=True)

    async def get_active_silences(self) -> list[Silence]:
        """获取活跃静默"""
        silences = await self._client.get_silences()
        return [s for s in silences if s.status == SilenceState.ACTIVE]

    async def generate_alert_report(self) -> dict[str, Any]:
        """生成告警报告"""
        alerts = await self.get_active_alerts()
        silences = await self.get_active_silences()

        by_severity = {}
        for alert in alerts:
            severity = alert.labels.get("severity", "unknown")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        by_name = {}
        for alert in alerts:
            name = alert.labels.get("alertname", "unknown")
            by_name[name] = by_name.get(name, 0) + 1

        return {
            "total_alerts": len(alerts),
            "total_silences": len(silences),
            "by_severity": by_severity,
            "by_name": by_name,
            "alerts": [
                {
                    "fingerprint": a.fingerprint,
                    "name": a.labels.get("alertname"),
                    "severity": a.labels.get("severity"),
                    "summary": a.annotations.get("summary"),
                    "starts_at": a.starts_at.isoformat() if a.starts_at else None,
                }
                for a in alerts[:10]  # 只返回前 10 个
            ],
            "silences": [
                {
                    "id": s.id,
                    "comment": s.comment,
                    "created_by": s.created_by,
                    "ends_at": s.ends_at.isoformat() if s.ends_at else None,
                }
                for s in silences
            ],
        }


# 全局实例
_alertmanager_client: AlertManagerClient | None = None
_alertmanager: AlertManager | None = None


def get_alertmanager_client(
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
    mock_mode: bool | None = None,
) -> AlertManagerClient:
    """获取全局 Alertmanager 客户端"""
    global _alertmanager_client
    if _alertmanager_client is None:
        import os
        url = base_url or os.getenv("ALERTMANAGER_URL", "http://localhost:9093")
        # 如果未指定 mock_mode，检查环境变量
        if mock_mode is None:
            mock_mode = os.getenv("ALERTMANAGER_MOCK_MODE", "").lower() in ("true", "1", "yes")
        _alertmanager_client = AlertManagerClient(url, timeout_seconds, mock_mode=mock_mode)
    return _alertmanager_client


def get_alertmanager() -> AlertManager:
    """获取全局告警管理器"""
    global _alertmanager
    if _alertmanager is None:
        _alertmanager = AlertManager(get_alertmanager_client())
    return _alertmanager