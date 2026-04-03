"""巡检规则配置"""

from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()


class CheckRule(BaseModel):
    """检查规则配置"""

    name: str
    enabled: bool = True
    description: str | None = None

    # 阈值配置
    thresholds: dict[str, Any] = Field(default_factory=dict)

    # 时间配置
    time_window_hours: int | None = None
    schedule_cron: str | None = None

    # 通知配置
    notify_on_pass: bool = False
    notify_on_warning: bool = True
    notify_on_error: bool = True
    notify_on_critical: bool = True

    # 其他配置
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatrolRules:
    """巡检规则管理"""

    def __init__(self) -> None:
        self._rules: dict[str, CheckRule] = {}
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载默认规则"""
        default_rules = [
            CheckRule(
                name="spark_failures",
                enabled=True,
                description="检查最近失败的 Spark 任务",
                thresholds={
                    "failure_threshold": 3,
                },
                time_window_hours=1,
                tags=["spark", "application"],
            ),
            CheckRule(
                name="queue_utilization",
                enabled=True,
                description="检查队列资源利用率",
                thresholds={
                    "warning_threshold": 70,
                    "critical_threshold": 90,
                },
                tags=["yunikorn", "resource"],
            ),
            CheckRule(
                name="node_health",
                enabled=True,
                description="检查 Kubernetes 节点健康状态",
                tags=["k8s", "infrastructure"],
            ),
            CheckRule(
                name="pod_restarts",
                enabled=True,
                description="检查频繁重启的 Pod",
                thresholds={
                    "restart_threshold": 5,
                },
                tags=["k8s", "pod"],
            ),
        ]

        for rule in default_rules:
            self._rules[rule.name] = rule

    def get_rule(self, name: str) -> CheckRule | None:
        """获取规则"""
        return self._rules.get(name)

    def list_rules(self) -> list[CheckRule]:
        """列出所有规则"""
        return list(self._rules.values())

    def update_rule(self, name: str, updates: dict[str, Any]) -> CheckRule | None:
        """更新规则"""
        rule = self._rules.get(name)
        if not rule:
            return None

        # 创建更新后的规则
        updated_data = rule.model_dump()
        updated_data.update(updates)
        updated_rule = CheckRule(**updated_data)

        self._rules[name] = updated_rule
        logger.info("rule_updated", name=name, updates=updates)

        return updated_rule

    def enable_rule(self, name: str) -> bool:
        """启用规则"""
        rule = self.update_rule(name, {"enabled": True})
        return rule is not None

    def disable_rule(self, name: str) -> bool:
        """禁用规则"""
        rule = self.update_rule(name, {"enabled": False})
        return rule is not None

    def set_threshold(self, name: str, threshold_name: str, value: Any) -> bool:
        """设置阈值"""
        rule = self._rules.get(name)
        if not rule:
            return False

        thresholds = rule.thresholds.copy()
        thresholds[threshold_name] = value

        self.update_rule(name, {"thresholds": thresholds})
        return True

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            name: rule.model_dump()
            for name, rule in self._rules.items()
        }


# 全局实例
_patrol_rules: PatrolRules | None = None


def get_patrol_rules() -> PatrolRules:
    """获取全局规则配置"""
    global _patrol_rules
    if _patrol_rules is None:
        _patrol_rules = PatrolRules()
    return _patrol_rules
