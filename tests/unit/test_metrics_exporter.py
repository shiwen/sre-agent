"""Prometheus Metrics Exporter 单元测试"""

import pytest
from datetime import datetime

from app.infrastructure.metrics_exporter import (
    MetricType,
    MetricValue,
    PrometheusMetric,
    MetricsRegistry,
    MetricsCollector,
    SRE_AGENT_METRICS,
    get_metrics_registry,
    get_metrics_collector,
)


@pytest.fixture
def registry():
    """创建注册表实例"""
    return MetricsRegistry()


@pytest.fixture
def collector(registry):
    """创建收集器实例"""
    return MetricsCollector(registry)


class TestMetricType:
    """MetricType 测试"""

    def test_metric_types(self):
        """测试指标类型"""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"


class TestPrometheusMetric:
    """PrometheusMetric 测试"""

    def test_metric_creation(self):
        """测试指标创建"""
        metric = PrometheusMetric(
            name="test_metric",
            type=MetricType.COUNTER,
            description="Test metric",
            labels=["label1", "label2"],
        )

        assert metric.name == "test_metric"
        assert metric.type == MetricType.COUNTER
        assert metric.description == "Test metric"
        assert metric.labels == ["label1", "label2"]


class TestMetricValue:
    """MetricValue 测试"""

    def test_value_creation(self):
        """测试值创建"""
        value = MetricValue(
            name="test_value",
            type=MetricType.GAUGE,
            value=42.0,
            labels=[("label1", "value1")],
        )

        assert value.name == "test_value"
        assert value.value == 42.0
        assert value.labels == [("label1", "value1")]


class TestMetricsRegistry:
    """MetricsRegistry 测试"""

    def test_default_metrics_registered(self, registry):
        """测试默认指标已注册"""
        metrics = registry.get_all_metrics()
        assert len(metrics) >= len(SRE_AGENT_METRICS)

        # 检查关键指标
        metric_names = [m.name for m in metrics]
        assert "sre_patrol_total" in metric_names
        assert "sre_spark_applications_total" in metric_names
        assert "sre_k8s_pods_total" in metric_names

    def test_register_custom_metric(self, registry):
        """测试注册自定义指标"""
        metric = PrometheusMetric(
            name="custom_metric",
            type=MetricType.GAUGE,
            description="Custom test metric",
        )

        registry.register(metric)

        registered = registry.get_metric("custom_metric")
        assert registered is not None
        assert registered.name == "custom_metric"

    def test_counter_operations(self, registry):
        """测试计数器操作"""
        registry.counter("sre_patrol_total", labels={"status": "success", "rule_name": "test_rule"})
        registry.counter("sre_patrol_total", labels={"status": "success", "rule_name": "test_rule"})

        # 验证值已增加
        values = registry._counter_values
        key = 'sre_patrol_total:rule_name=test_rule,status=success'
        assert values.get(key, 0) == 2.0

    def test_gauge_operations(self, registry):
        """测试 gauge 操作"""
        registry.gauge("sre_k8s_pods_total", value=10, labels={"namespace": "default", "status": "running"})

        values = registry._gauge_values
        key = 'sre_k8s_pods_total:namespace=default,status=running'
        assert values.get(key, 0) == 10

    def test_gauge_set_operations(self, registry):
        """测试 gauge set 操作"""
        registry.set("sre_k8s_pods_total", value=15, labels={"namespace": "default", "status": "running"})
        registry.set("sre_k8s_pods_total", value=20, labels={"namespace": "default", "status": "running"})

        values = registry._gauge_values
        key = 'sre_k8s_pods_total:namespace=default,status=running'
        assert values.get(key, 0) == 20

    def test_histogram_operations(self, registry):
        """测试 histogram 操作"""
        registry.histogram("sre_patrol_duration_seconds", value=0.1, labels={"rule_name": "test"})
        registry.histogram("sre_patrol_duration_seconds", value=0.5, labels={"rule_name": "test"})
        registry.histogram("sre_patrol_duration_seconds", value=2.0, labels={"rule_name": "test"})

        key = 'sre_patrol_duration_seconds:rule_name=test'
        counts = registry._histogram_counts.get(key)

        assert counts is not None
        assert counts["count"] == 3
        assert counts["sum"] == 2.6

    def test_inc_and_dec_operations(self, registry):
        """测试 inc 和 dec 操作"""
        registry.gauge("sre_k8s_pods_total", value=10, labels={"namespace": "default", "status": "running"})
        registry.inc("sre_patrol_total", labels={"status": "success", "rule_name": "test"})
        registry.dec("sre_k8s_pods_total", labels={"namespace": "default", "status": "running"})

    def test_export_prometheus_format(self, registry):
        """测试 Prometheus 格式导出"""
        registry.counter("sre_patrol_total", labels={"status": "success", "rule_name": "test_rule"})
        registry.gauge("sre_k8s_pods_total", value=10, labels={"namespace": "default", "status": "running"})

        exported = registry.export_prometheus_format()

        assert "# HELP sre_patrol_total" in exported
        assert "# TYPE sre_patrol_total counter" in exported
        assert "sre_patrol_total" in exported
        assert "sre_k8s_pods_total" in exported

    def test_export_histogram_format(self, registry):
        """测试 histogram 格式导出"""
        registry.histogram("sre_patrol_duration_seconds", value=1.0, labels={"rule_name": "test"})

        exported = registry.export_prometheus_format()

        assert "# TYPE sre_patrol_duration_seconds histogram" in exported
        assert "sre_patrol_duration_seconds_bucket" in exported
        assert "sre_patrol_duration_seconds_sum" in exported
        assert "sre_patrol_duration_seconds_count" in exported
        assert 'le="+Inf"' in exported

    def test_clear_metrics(self, registry):
        """测试清除指标"""
        registry.counter("sre_patrol_total", labels={"status": "success", "rule_name": "test"})
        registry.gauge("sre_k8s_pods_total", value=10, labels={"namespace": "default", "status": "running"})

        registry.clear()

        assert len(registry._counter_values) == 0
        assert len(registry._gauge_values) == 0
        assert len(registry._histogram_counts) == 0

    def test_get_summary(self, registry):
        """测试获取摘要"""
        summary = registry.get_summary()

        assert "total_metrics" in summary
        assert "metrics_by_type" in summary
        assert summary["total_metrics"] >= len(SRE_AGENT_METRICS)


class TestMetricsCollector:
    """MetricsCollector 测试"""

    @pytest.mark.asyncio
    async def test_collect_patrol_metrics(self, collector, registry):
        """测试收集 patrol 指标"""
        patrol_results = {
            "check_memory": {
                "status": "success",
                "issues": [{"severity": "high"}, {"severity": "medium"}],
                "duration_seconds": 0.5,
                "timestamp": 1712134800.0,
            }
        }

        await collector.collect_patrol_metrics(patrol_results)

        # 验证指标被记录
        assert len(registry._counter_values) > 0
        assert len(registry._gauge_values) > 0

    @pytest.mark.asyncio
    async def test_collect_spark_metrics(self, collector, registry):
        """测试收集 Spark 指标"""
        spark_apps = [
            {
                "id": "app-001",
                "name": "test-app",
                "status": "RUNNING",
                "spark_user": "testuser",
                "duration_ms": 60000,
                "failed_tasks": 2,
            }
        ]

        await collector.collect_spark_metrics(spark_apps)

        # 验证指标被记录
        assert len(registry._gauge_values) > 0

    @pytest.mark.asyncio
    async def test_collect_yunikorn_metrics(self, collector, registry):
        """测试收集 YuniKorn 指标"""
        queue_data = [
            {
                "name": "root.default",
                "applications": {"running": 5, "pending": 2},
                "memory_allocated": 1024000000,
                "memory_used": 512000000,
                "cpu_allocated": 10,
                "cpu_used": 5,
            }
        ]

        await collector.collect_yunikorn_metrics(queue_data)

        # 验证指标被记录
        assert len(registry._gauge_values) > 0

    @pytest.mark.asyncio
    async def test_collect_k8s_metrics(self, collector, registry):
        """测试收集 Kubernetes 指标"""
        k8s_data = {
            "pods": {
                "default": {"running": 10, "pending": 2},
                "kube-system": {"running": 5},
            },
            "nodes": {"ready": 3, "not_ready": 0},
            "node_usage": {
                "node-1": {"cpu_percent": 50.0, "memory_percent": 60.0},
            },
        }

        await collector.collect_k8s_metrics(k8s_data)

        # 验证指标被记录
        assert len(registry._gauge_values) > 0

    @pytest.mark.asyncio
    async def test_collect_agent_metrics(self, collector, registry):
        """测试收集 Agent 指标"""
        agent_data = {
            "sessions_total": 10,
            "messages_total": 100,
            "tool_calls": {
                "spark_list": {"success": 50, "error": 2},
            },
            "llm_tokens_input": 10000,
            "llm_tokens_output": 5000,
        }

        await collector.collect_agent_metrics(agent_data)

        # 验证指标被记录
        assert len(registry._counter_values) > 0


class TestSingletonFunctions:
    """单例函数测试"""

    def test_get_metrics_registry_singleton(self):
        """测试获取注册表单例"""
        registry1 = get_metrics_registry()
        registry2 = get_metrics_registry()

        assert registry1 is registry2

    def test_get_metrics_collector(self):
        """测试获取收集器"""
        collector = get_metrics_collector()
        assert collector is not None


class TestSREAgentMetrics:
    """SRE Agent 指标定义测试"""

    def test_patrol_metrics_defined(self):
        """测试 patrol 指标定义"""
        metric_names = [m.name for m in SRE_AGENT_METRICS]
        assert "sre_patrol_total" in metric_names
        assert "sre_patrol_duration_seconds" in metric_names
        assert "sre_patrol_issues_found" in metric_names

    def test_spark_metrics_defined(self):
        """测试 Spark 指标定义"""
        metric_names = [m.name for m in SRE_AGENT_METRICS]
        assert "sre_spark_applications_total" in metric_names
        assert "sre_spark_application_duration_seconds" in metric_names
        assert "sre_spark_executor_memory_used_bytes" in metric_names

    def test_yunikorn_metrics_defined(self):
        """测试 YuniKorn 指标定义"""
        metric_names = [m.name for m in SRE_AGENT_METRICS]
        assert "sre_yunikorn_queue_applications_total" in metric_names
        assert "sre_yunikorn_queue_memory_used_bytes" in metric_names
        assert "sre_yunikorn_queue_cpu_used_cores" in metric_names

    def test_k8s_metrics_defined(self):
        """测试 Kubernetes 指标定义"""
        metric_names = [m.name for m in SRE_AGENT_METRICS]
        assert "sre_k8s_pods_total" in metric_names
        assert "sre_k8s_nodes_total" in metric_names
        assert "sre_k8s_node_cpu_usage_percent" in metric_names

    def test_agent_metrics_defined(self):
        """测试 Agent 指标定义"""
        metric_names = [m.name for m in SRE_AGENT_METRICS]
        assert "sre_agent_chat_sessions_total" in metric_names
        assert "sre_agent_tool_calls_total" in metric_names
        assert "sre_agent_llm_tokens_total" in metric_names