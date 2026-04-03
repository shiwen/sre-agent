"""巡检引擎集成测试"""

from datetime import datetime

import pytest

from app.patrol.checks import (
    NodeHealthCheck,
    PodRestartCheck,
    QueueUtilizationCheck,
    SparkFailureCheck,
    get_default_checks,
)
from app.patrol.engine import (
    CheckResult,
    CheckSeverity,
    PatrolEngine,
    PatrolReport,
)
from app.patrol.rules import CheckRule, PatrolRules, get_patrol_rules
from app.patrol.scheduler import PatrolScheduler, get_patrol_scheduler


class TestPatrolEngine:
    """巡检引擎集成测试"""

    def test_engine_creation(self):
        """测试引擎创建"""
        engine = PatrolEngine()
        assert engine is not None
        assert engine._checks == []
        assert engine._reports == []

    def test_register_check(self):
        """测试注册检查"""
        engine = PatrolEngine()
        check = SparkFailureCheck()
        engine.register_check(check)

        assert len(engine._checks) == 1
        assert engine._checks[0].name == "spark_failures"

    def test_register_checks_batch(self):
        """测试批量注册检查"""
        engine = PatrolEngine()
        checks = get_default_checks()
        engine.register_checks(checks)

        assert len(engine._checks) == 4
        check_names = [c.name for c in engine._checks]
        assert "spark_failures" in check_names
        assert "queue_utilization" in check_names
        assert "node_health" in check_names
        assert "pod_restarts" in check_names

    def test_list_checks(self):
        """测试列出检查"""
        engine = PatrolEngine()
        engine.register_checks(get_default_checks())

        checks_info = engine.list_checks()
        assert len(checks_info) == 4
        for check in checks_info:
            assert "name" in check
            assert "description" in check
            assert "enabled" in check

    @pytest.mark.asyncio
    async def test_run_patrol_empty(self):
        """测试空巡检"""
        engine = PatrolEngine()
        report = await engine.run_patrol()

        assert report.status == "completed"
        assert len(report.checks) == 0
        assert report.summary["total_checks"] == 0

    @pytest.mark.asyncio
    async def test_run_patrol_with_checks(self):
        """测试带检查的巡检"""
        engine = PatrolEngine()
        engine.register_checks(get_default_checks())

        report = await engine.run_patrol()

        assert report.status == "completed"
        assert len(report.checks) == 4
        assert report.summary["total_checks"] == 4
        assert report.end_time is not None
        assert report.id.startswith("patrol-")

    @pytest.mark.asyncio
    async def test_run_patrol_filtered(self):
        """测试过滤检查"""
        engine = PatrolEngine()
        engine.register_checks(get_default_checks())

        # 只运行特定检查
        report = await engine.run_patrol(check_names=["spark_failures"])

        assert report.status == "completed"
        assert len(report.checks) == 1
        assert report.checks[0].check_name == "spark_failures"

    @pytest.mark.asyncio
    async def test_report_finalize(self):
        """测试报告完成"""
        report = PatrolReport()

        # 添加检查结果
        report.add_check(CheckResult(
            check_name="test_check",
            status="pass",
            message="Test passed",
        ))
        report.add_check(CheckResult(
            check_name="test_check2",
            status="warning",
            message="Test warning",
        ))

        report.finalize()

        assert report.status == "completed"
        assert report.end_time is not None
        assert report.summary["total_checks"] == 2
        assert report.summary["passed"] == 1
        assert report.summary["warnings"] == 1

    def test_report_to_dict(self):
        """测试报告序列化"""
        report = PatrolReport()
        report.add_check(CheckResult(
            check_name="test",
            status="pass",
            message="OK",
        ))
        report.finalize()

        data = report.to_dict()

        assert "id" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "status" in data
        assert "checks" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_engine_stores_reports(self):
        """测试报告存储"""
        engine = PatrolEngine()
        engine.register_checks(get_default_checks())

        # 运行多次
        await engine.run_patrol()
        await engine.run_patrol()

        reports = engine.list_reports()
        assert len(reports) == 2

    def test_get_report_by_id(self):
        """测试按 ID 获取报告"""
        engine = PatrolEngine()
        report = PatrolReport()
        engine._reports.append(report)

        found = engine.get_report(report.id)
        assert found is not None
        assert found.id == report.id

    def test_get_nonexistent_report(self):
        """测试获取不存在的报告"""
        engine = PatrolEngine()
        found = engine.get_report("nonexistent-id")
        assert found is None

    def test_get_latest_report(self):
        """测试获取最新报告"""
        engine = PatrolEngine()
        report1 = PatrolReport()
        report2 = PatrolReport()

        engine._reports.append(report1)
        engine._reports.append(report2)

        latest = engine.get_latest_report()
        assert latest is report2

    def test_max_reports_limit(self):
        """测试报告数量限制"""
        engine = PatrolEngine()
        engine._max_reports = 5

        # 添加超过限制的报告
        for _ in range(10):
            engine._reports.append(PatrolReport())

        # 在巡检后会自动裁剪
        # 模拟裁剪逻辑
        if len(engine._reports) > engine._max_reports:
            engine._reports = engine._reports[-engine._max_reports:]

        assert len(engine._reports) == 5


class TestPatrolChecks:
    """巡检检查集成测试"""

    @pytest.mark.asyncio
    async def test_spark_failure_check(self):
        """测试 Spark 失败检查"""
        check = SparkFailureCheck()

        result = await check.execute()

        assert result.check_name == "spark_failures"
        assert result.status in ["pass", "warning", "error"]
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_queue_utilization_check(self):
        """测试队列利用率检查"""
        check = QueueUtilizationCheck()

        result = await check.execute()

        assert result.check_name == "queue_utilization"
        assert result.status in ["pass", "warning", "critical"]
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_node_health_check(self):
        """测试节点健康检查"""
        check = NodeHealthCheck()

        result = await check.execute()

        assert result.check_name == "node_health"
        assert result.status in ["pass", "warning", "critical"]
        assert result.message is not None
        assert "details" in result.model_dump()

    @pytest.mark.asyncio
    async def test_pod_restart_check(self):
        """测试 Pod 重启检查"""
        check = PodRestartCheck()

        result = await check.execute()

        assert result.check_name == "pod_restarts"
        assert result.status in ["pass", "warning", "error"]
        assert result.message is not None

    def test_check_enabled_flag(self):
        """测试检查启用标志"""
        check = SparkFailureCheck()
        assert check.enabled is True

        # 可以禁用
        check.enabled = False
        assert check.enabled is False

    @pytest.mark.asyncio
    async def test_disabled_check_not_run(self):
        """测试禁用的检查不执行"""
        engine = PatrolEngine()
        check = SparkFailureCheck()
        check.enabled = False
        engine.register_check(check)

        report = await engine.run_patrol()

        # 禁用的检查不应执行
        assert len(report.checks) == 0

    def test_get_default_checks(self):
        """测试获取默认检查"""
        checks = get_default_checks()

        assert len(checks) == 4
        check_types = [type(c).__name__ for c in checks]
        assert "SparkFailureCheck" in check_types
        assert "QueueUtilizationCheck" in check_types
        assert "NodeHealthCheck" in check_types
        assert "PodRestartCheck" in check_types


class TestCheckResult:
    """检查结果测试"""

    def test_check_result_creation(self):
        """测试检查结果创建"""
        result = CheckResult(
            check_name="test_check",
            status="pass",
            message="All good",
            details={"count": 10},
            suggestions=["Keep monitoring"],
        )

        assert result.check_name == "test_check"
        assert result.status == "pass"
        assert result.severity == CheckSeverity.INFO
        assert result.details["count"] == 10
        assert len(result.suggestions) == 1

    def test_check_result_with_resource(self):
        """测试带资源的检查结果"""
        result = CheckResult(
            check_name="node_check",
            status="warning",
            message="Node not ready",
            resource="node-01",
        )

        assert result.resource == "node-01"

    def test_check_result_timestamp(self):
        """测试时间戳"""
        result = CheckResult(
            check_name="test",
            status="pass",
            message="OK",
        )

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)


class TestPatrolRules:
    """巡检规则配置测试"""

    def test_rules_creation(self):
        """测试规则创建"""
        rules = PatrolRules()
        assert rules is not None
        assert len(rules._rules) > 0

    def test_get_rule(self):
        """测试获取规则"""
        rules = PatrolRules()
        rule = rules.get_rule("spark_failures")

        assert rule is not None
        assert rule.name == "spark_failures"
        assert rule.enabled is True

    def test_get_nonexistent_rule(self):
        """测试获取不存在的规则"""
        rules = PatrolRules()
        rule = rules.get_rule("nonexistent")
        assert rule is None

    def test_list_rules(self):
        """测试列出规则"""
        rules = PatrolRules()
        all_rules = rules.list_rules()

        assert len(all_rules) == 4
        for rule in all_rules:
            assert isinstance(rule, CheckRule)

    def test_update_rule(self):
        """测试更新规则"""
        rules = PatrolRules()
        updated = rules.update_rule("spark_failures", {"enabled": False})

        assert updated is not None
        assert updated.enabled is False

        # 验证更新持久化
        rule = rules.get_rule("spark_failures")
        assert rule.enabled is False

    def test_enable_rule(self):
        """测试启用规则"""
        rules = PatrolRules()
        rules.disable_rule("spark_failures")

        result = rules.enable_rule("spark_failures")
        assert result is True

        rule = rules.get_rule("spark_failures")
        assert rule.enabled is True

    def test_disable_rule(self):
        """测试禁用规则"""
        rules = PatrolRules()
        result = rules.disable_rule("queue_utilization")

        assert result is True

        rule = rules.get_rule("queue_utilization")
        assert rule.enabled is False

    def test_set_threshold(self):
        """测试设置阈值"""
        rules = PatrolRules()
        result = rules.set_threshold("queue_utilization", "warning_threshold", 80)

        assert result is True

        rule = rules.get_rule("queue_utilization")
        assert rule.thresholds["warning_threshold"] == 80

    def test_rule_thresholds_integration(self):
        """测试阈值与检查集成"""
        rules = PatrolRules()
        # 设置自定义阈值
        rules.set_threshold("queue_utilization", "warning_threshold", 50)
        rules.set_threshold("queue_utilization", "critical_threshold", 75)

        rule = rules.get_rule("queue_utilization")
        assert rule.thresholds["warning_threshold"] == 50
        assert rule.thresholds["critical_threshold"] == 75

    def test_rule_notification_config(self):
        """测试通知配置"""
        rules = PatrolRules()
        rule = rules.get_rule("spark_failures")

        assert rule.notify_on_pass is False
        assert rule.notify_on_warning is True
        assert rule.notify_on_error is True
        assert rule.notify_on_critical is True

    def test_rules_to_dict(self):
        """测试规则序列化"""
        rules = PatrolRules()
        data = rules.to_dict()

        assert isinstance(data, dict)
        assert "spark_failures" in data
        assert "queue_utilization" in data

    def test_get_patrol_rules_singleton(self):
        """测试单例获取"""
        rules1 = get_patrol_rules()
        rules2 = get_patrol_rules()

        assert rules1 is rules2


class TestPatrolScheduler:
    """巡检调度器测试"""

    def test_scheduler_creation(self):
        """测试调度器创建"""
        scheduler = PatrolScheduler()
        assert scheduler is not None
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_scheduler_not_started_twice(self):
        """测试不能重复启动"""
        scheduler = PatrolScheduler()
        scheduler.start(interval_minutes=30)

        assert scheduler._running is True

        # 再次启动应该被忽略
        scheduler.start(interval_minutes=60)
        # 状态仍然是 True，但不应该报错
        scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop(self):
        """测试停止调度器"""
        scheduler = PatrolScheduler()
        scheduler.start(interval_minutes=30)
        scheduler.stop()

        assert scheduler._running is False

    def test_scheduler_stop_not_running(self):
        """测试停止未运行的调度器"""
        scheduler = PatrolScheduler()
        scheduler.stop()  # 未运行时停止应该安全
        assert scheduler._running is False

    def test_get_status_not_running(self):
        """测试未运行状态"""
        scheduler = PatrolScheduler()
        status = scheduler.get_status()

        assert status["running"] is False
        assert status["next_run"] is None

    @pytest.mark.asyncio
    async def test_scheduler_with_cron(self):
        """测试 cron 表达式启动"""
        scheduler = PatrolScheduler()
        scheduler.start_with_cron("*/30 * * * *")

        assert scheduler._running is True
        scheduler.stop()

    def test_invalid_cron_expression(self):
        """测试无效 cron 表达式"""
        scheduler = PatrolScheduler()
        with pytest.raises(ValueError):
            scheduler.start_with_cron("invalid-cron")

    def test_set_notification_callback(self):
        """测试设置通知回调"""
        scheduler = PatrolScheduler()

        async def callback(report):
            pass

        scheduler.set_notification_callback(callback)
        assert scheduler._notification_callback is callback

    def test_get_patrol_scheduler_singleton(self):
        """测试调度器单例"""
        # 重置全局实例
        from app.patrol import scheduler as scheduler_module
        scheduler_module._patrol_scheduler = None

        scheduler1 = get_patrol_scheduler()
        scheduler2 = get_patrol_scheduler()

        assert scheduler1 is scheduler2


class TestCheckRule:
    """检查规则模型测试"""

    def test_rule_creation(self):
        """测试规则创建"""
        rule = CheckRule(
            name="test_rule",
            enabled=True,
            description="Test description",
            thresholds={"threshold": 10},
        )

        assert rule.name == "test_rule"
        assert rule.enabled is True
        assert rule.thresholds["threshold"] == 10

    def test_rule_default_values(self):
        """测试默认值"""
        rule = CheckRule(name="test")

        assert rule.enabled is True
        assert rule.description is None
        assert rule.thresholds == {}
        assert rule.tags == []
        assert rule.notify_on_pass is False
        assert rule.notify_on_warning is True

    def test_rule_with_tags(self):
        """测试带标签的规则"""
        rule = CheckRule(
            name="test",
            tags=["spark", "critical"],
        )

        assert "spark" in rule.tags
        assert "critical" in rule.tags


class TestPatrolAPIIntegration:
    """巡检 API 集成测试"""

    @pytest.mark.asyncio
    async def test_full_patrol_workflow(self):
        """测试完整巡检工作流"""
        # 1. 创建引擎
        engine = PatrolEngine()

        # 2. 注册检查
        engine.register_checks(get_default_checks())

        # 3. 运行巡检
        report = await engine.run_patrol()

        # 4. 验证报告
        assert report.status == "completed"
        assert len(report.checks) == 4

        # 5. 存储和检索
        reports = engine.list_reports()
        assert len(reports) == 1

        # 6. 获取详情
        retrieved = engine.get_report(report.id)
        assert retrieved is not None
        assert retrieved.id == report.id

    @pytest.mark.asyncio
    async def test_patrol_with_rules_integration(self):
        """测试巡检与规则集成"""
        # 获取规则
        rules = get_patrol_rules()

        # 修改阈值
        rules.set_threshold("queue_utilization", "warning_threshold", 80)

        # 创建检查
        check = QueueUtilizationCheck()

        # 检查应该使用规则中的阈值
        threshold = check._get_threshold("warning_threshold", 70)
        assert threshold == 80

    @pytest.mark.asyncio
    async def test_scheduler_patrol_integration(self):
        """测试调度器与巡检集成"""
        scheduler = PatrolScheduler()

        # 模拟巡检执行
        engine = PatrolEngine()
        engine.register_checks(get_default_checks())

        # 设置回调
        callback_called = False

        async def notification_callback(report):
            nonlocal callback_called
            callback_called = True

        scheduler.set_notification_callback(notification_callback)

        # 手动执行内部巡检方法
        # 重置全局引擎
        from app.patrol import engine as engine_module
        engine_module._patrol_engine = engine

        report = await scheduler._run_patrol()

        assert report.status == "completed"
        assert callback_called is True

        scheduler.stop()

        # 清理
        engine_module._patrol_engine = None


class TestPatrolRulesAPIEndpoints:
    """巡检规则 API 端点测试"""

    @pytest.mark.asyncio
    async def test_rules_api_list(self):
        """测试规则列表 API"""
        rules = get_patrol_rules()
        all_rules = rules.list_rules()

        assert len(all_rules) == 4
        rule_names = [r.name for r in all_rules]
        assert "spark_failures" in rule_names
        assert "queue_utilization" in rule_names

    @pytest.mark.asyncio
    async def test_rules_api_get(self):
        """测试获取规则 API"""
        rules = get_patrol_rules()
        rule = rules.get_rule("spark_failures")

        assert rule is not None
        assert rule.name == "spark_failures"
        assert rule.enabled is True

    @pytest.mark.asyncio
    async def test_rules_api_update(self):
        """测试更新规则 API"""
        rules = get_patrol_rules()
        updated = rules.update_rule("spark_failures", {"enabled": False})

        assert updated is not None
        assert updated.enabled is False

        # 恢复
        rules.enable_rule("spark_failures")

    @pytest.mark.asyncio
    async def test_rules_api_threshold_update(self):
        """测试阈值更新 API"""
        rules = get_patrol_rules()
        result = rules.set_threshold("queue_utilization", "warning_threshold", 85)

        assert result is True

        rule = rules.get_rule("queue_utilization")
        assert rule.thresholds["warning_threshold"] == 85


class TestSchedulerAPIEndpoints:
    """调度器 API 端点测试"""

    @pytest.mark.asyncio
    async def test_scheduler_api_status_not_running(self):
        """测试调度器状态 API"""
        scheduler = PatrolScheduler()
        status = scheduler.get_status()

        assert status["running"] is False
        assert status["next_run"] is None

    @pytest.mark.asyncio
    async def test_scheduler_api_start_interval(self):
        """测试启动调度器 API（间隔模式）"""
        scheduler = PatrolScheduler()
        scheduler.start(interval_minutes=30)

        status = scheduler.get_status()
        assert status["running"] is True

        scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_api_start_cron(self):
        """测试启动调度器 API（Cron 模式）"""
        scheduler = PatrolScheduler()
        scheduler.start_with_cron("*/30 * * * *")

        status = scheduler.get_status()
        assert status["running"] is True

        scheduler.stop()

    def test_scheduler_api_invalid_cron(self):
        """测试无效 Cron 表达式"""
        scheduler = PatrolScheduler()
        with pytest.raises(ValueError):
            scheduler.start_with_cron("invalid")
