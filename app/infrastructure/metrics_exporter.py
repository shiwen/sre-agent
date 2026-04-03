"""Prometheus 指标导出器

为 SRE Agent 提供 Prometheus 格式的指标导出功能。
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()


class MetricType(str, Enum):
    """指标类型"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricLabel:
    """指标标签"""

    name: str
    value: str


class MetricValue(BaseModel):
    """指标值"""

    name: str
    type: MetricType
    value: float
    labels: list[tuple[str, str]] = Field(default_factory=list)
    timestamp: float | None = None
    description: str | None = None
    unit: str | None = None


class PrometheusMetric(BaseModel):
    """Prometheus 指标定义"""

    name: str
    type: MetricType
    description: str
    unit: str | None = None
    labels: list[str] = Field(default_factory=list)


# SRE Agent 指标定义
SRE_AGENT_METRICS = [
    # Patrol 指标
    PrometheusMetric(
        name="sre_patrol_total",
        type=MetricType.COUNTER,
        description="Total number of patrol checks executed",
        labels=["status", "rule_name"],
    ),
    PrometheusMetric(
        name="sre_patrol_duration_seconds",
        type=MetricType.HISTOGRAM,
        description="Duration of patrol checks in seconds",
        unit="seconds",
        labels=["rule_name"],
    ),
    PrometheusMetric(
        name="sre_patrol_issues_found",
        type=MetricType.GAUGE,
        description="Number of issues found during patrol",
        labels=["rule_name", "severity"],
    ),
    PrometheusMetric(
        name="sre_patrol_last_run_timestamp",
        type=MetricType.GAUGE,
        description="Timestamp of last patrol run",
        labels=["rule_name"],
    ),

    # Spark 指标
    PrometheusMetric(
        name="sre_spark_applications_total",
        type=MetricType.GAUGE,
        description="Total number of Spark applications",
        labels=["status", "user"],
    ),
    PrometheusMetric(
        name="sre_spark_application_duration_seconds",
        type=MetricType.HISTOGRAM,
        description="Duration of Spark applications in seconds",
        unit="seconds",
        labels=["status", "app_name"],
    ),
    PrometheusMetric(
        name="sre_spark_application_failed_tasks",
        type=MetricType.GAUGE,
        description="Number of failed tasks in Spark application",
        labels=["app_id", "stage_id"],
    ),
    PrometheusMetric(
        name="sre_spark_executor_memory_used_bytes",
        type=MetricType.GAUGE,
        description="Memory used by Spark executor",
        unit="bytes",
        labels=["app_id", "executor_id"],
    ),
    PrometheusMetric(
        name="sre_spark_stage_shuffle_read_bytes",
        type=MetricType.GAUGE,
        description="Shuffle read bytes for Spark stage",
        unit="bytes",
        labels=["app_id", "stage_id"],
    ),
    PrometheusMetric(
        name="sre_spark_stage_shuffle_write_bytes",
        type=MetricType.GAUGE,
        description="Shuffle write bytes for Spark stage",
        unit="bytes",
        labels=["app_id", "stage_id"],
    ),

    # YuniKorn 指标
    PrometheusMetric(
        name="sre_yunikorn_queue_applications_total",
        type=MetricType.GAUGE,
        description="Total number of applications in YuniKorn queue",
        labels=["queue_name", "state"],
    ),
    PrometheusMetric(
        name="sre_yunikorn_queue_memory_allocated_bytes",
        type=MetricType.GAUGE,
        description="Memory allocated to YuniKorn queue",
        unit="bytes",
        labels=["queue_name"],
    ),
    PrometheusMetric(
        name="sre_yunikorn_queue_memory_used_bytes",
        type=MetricType.GAUGE,
        description="Memory used by YuniKorn queue",
        unit="bytes",
        labels=["queue_name"],
    ),
    PrometheusMetric(
        name="sre_yunikorn_queue_cpu_allocated_cores",
        type=MetricType.GAUGE,
        description="CPU cores allocated to YuniKorn queue",
        unit="cores",
        labels=["queue_name"],
    ),
    PrometheusMetric(
        name="sre_yunikorn_queue_cpu_used_cores",
        type=MetricType.GAUGE,
        description="CPU cores used by YuniKorn queue",
        unit="cores",
        labels=["queue_name"],
    ),

    # Kubernetes 指标
    PrometheusMetric(
        name="sre_k8s_pods_total",
        type=MetricType.GAUGE,
        description="Total number of Kubernetes pods",
        labels=["namespace", "status"],
    ),
    PrometheusMetric(
        name="sre_k8s_nodes_total",
        type=MetricType.GAUGE,
        description="Total number of Kubernetes nodes",
        labels=["status"],
    ),
    PrometheusMetric(
        name="sre_k8s_node_cpu_usage_percent",
        type=MetricType.GAUGE,
        description="CPU usage percentage on Kubernetes node",
        unit="percent",
        labels=["node_name"],
    ),
    PrometheusMetric(
        name="sre_k8s_node_memory_usage_percent",
        type=MetricType.GAUGE,
        description="Memory usage percentage on Kubernetes node",
        unit="percent",
        labels=["node_name"],
    ),

    # Agent 指标
    PrometheusMetric(
        name="sre_agent_chat_sessions_total",
        type=MetricType.COUNTER,
        description="Total number of chat sessions",
    ),
    PrometheusMetric(
        name="sre_agent_chat_messages_total",
        type=MetricType.COUNTER,
        description="Total number of chat messages processed",
        labels=["session_id"],
    ),
    PrometheusMetric(
        name="sre_agent_tool_calls_total",
        type=MetricType.COUNTER,
        description="Total number of tool calls",
        labels=["tool_name", "status"],
    ),
    PrometheusMetric(
        name="sre_agent_tool_duration_seconds",
        type=MetricType.HISTOGRAM,
        description="Duration of tool calls in seconds",
        unit="seconds",
        labels=["tool_name"],
    ),
    PrometheusMetric(
        name="sre_agent_llm_tokens_total",
        type=MetricType.COUNTER,
        description="Total number of LLM tokens used",
        labels=["type"],  # input, output
    ),
    PrometheusMetric(
        name="sre_agent_llm_latency_seconds",
        type=MetricType.HISTOGRAM,
        description="Latency of LLM calls in seconds",
        unit="seconds",
    ),
]


class MetricsRegistry:
    """指标注册表"""

    def __init__(self) -> None:
        self._metrics: dict[str, PrometheusMetric] = {}
        self._values: dict[str, list[MetricValue]] = {}
        self._counter_values: dict[str, float] = {}
        self._gauge_values: dict[str, float] = {}
        self._histogram_buckets: dict[str, list[float]] = {}
        self._histogram_counts: dict[str, dict[str, int]] = {}

        # 注册默认指标
        for metric in SRE_AGENT_METRICS:
            self.register(metric)

    def register(self, metric: PrometheusMetric) -> None:
        """注册指标"""
        self._metrics[metric.name] = metric
        self._values[metric.name] = []

        # 初始化 histogram buckets
        if metric.type == MetricType.HISTOGRAM:
            self._histogram_buckets[metric.name] = [
                0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10
            ]
            self._histogram_counts[metric.name] = {"bucket_counts": [], "sum": 0.0, "count": 0}

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """增加计数器"""
        if name not in self._metrics:
            logger.warning("metric_not_registered", name=name)
            return

        key = self._make_key(name, labels or {})
        self._counter_values[key] = self._counter_values.get(key, 0.0) + value

        metric_value = MetricValue(
            name=name,
            type=MetricType.COUNTER,
            value=self._counter_values[key],
            labels=list(labels.items()) if labels else [],
            timestamp=time.time(),
        )
        self._values[name].append(metric_value)

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """设置 gauge 值"""
        if name not in self._metrics:
            logger.warning("metric_not_registered", name=name)
            return

        key = self._make_key(name, labels or {})
        self._gauge_values[key] = value

        metric_value = MetricValue(
            name=name,
            type=MetricType.GAUGE,
            value=value,
            labels=list(labels.items()) if labels else [],
            timestamp=time.time(),
        )
        self._values[name].append(metric_value)

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """记录 histogram 值"""
        if name not in self._metrics:
            logger.warning("metric_not_registered", name=name)
            return

        key = self._make_key(name, labels or {})

        # 更新 histogram 统计
        if key not in self._histogram_counts:
            self._histogram_counts[key] = {
                "bucket_counts": [0] * len(self._histogram_buckets[name]),
                "sum": 0.0,
                "count": 0,
            }

        counts = self._histogram_counts[key]
        counts["sum"] += value
        counts["count"] += 1

        # 更新 bucket counts
        buckets = self._histogram_buckets[name]
        for i, bucket in enumerate(buckets):
            if value <= bucket:
                counts["bucket_counts"][i] += 1

        metric_value = MetricValue(
            name=name,
            type=MetricType.HISTOGRAM,
            value=value,
            labels=list(labels.items()) if labels else [],
            timestamp=time.time(),
        )
        self._values[name].append(metric_value)

    def inc(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        """增加计数器（别名）"""
        self.counter(name, amount, labels)

    def dec(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        """减少 gauge 值"""
        key = self._make_key(name, labels or {})
        current = self._gauge_values.get(key, 0.0)
        self.gauge(name, current - amount, labels)

    def set(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """设置 gauge 值（别名）"""
        self.gauge(name, value, labels)

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """记录 histogram 值（别名）"""
        self.histogram(name, value, labels)

    def _make_key(self, name: str, labels: dict[str, str]) -> str:
        """生成唯一键"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}:{label_str}"

    def get_metric(self, name: str) -> PrometheusMetric | None:
        """获取指标定义"""
        return self._metrics.get(name)

    def get_all_metrics(self) -> list[PrometheusMetric]:
        """获取所有指标定义"""
        return list(self._metrics.values())

    def export_prometheus_format(self) -> str:
        """导出 Prometheus 格式"""
        lines = []

        for name, metric in self._metrics.items():
            # 写入 HELP 和 TYPE
            lines.append(f"# HELP {name} {metric.description}")
            if metric.unit:
                lines.append(f"# UNIT {name} {metric.unit}")
            lines.append(f"# TYPE {name} {metric.type.value}")

            # 写入值
            if metric.type == MetricType.COUNTER:
                for key, value in self._counter_values.items():
                    if key.startswith(name):
                        labels = self._extract_labels(key)
                        label_str = self._format_labels(labels)
                        lines.append(f"{name}{label_str} {value}")

            elif metric.type == MetricType.GAUGE:
                for key, value in self._gauge_values.items():
                    if key.startswith(name):
                        labels = self._extract_labels(key)
                        label_str = self._format_labels(labels)
                        lines.append(f"{name}{label_str} {value}")

            elif metric.type == MetricType.HISTOGRAM:
                buckets = self._histogram_buckets.get(name, [])
                for key, count_data in self._histogram_counts.items():
                    # 精确匹配 metric name
                    if not key.startswith(name + ":") and key != name:
                        continue

                    counts = count_data
                    # 确保 bucket_counts 长度与 buckets 一致
                    if len(counts["bucket_counts"]) != len(buckets):
                        counts["bucket_counts"] = counts["bucket_counts"][:len(buckets)]
                        counts["bucket_counts"].extend([0] * (len(buckets) - len(counts["bucket_counts"])))

                    labels = self._extract_labels(key)
                    label_str = self._format_labels(labels)

                    # Bucket 行
                    cumulative = 0
                    for i, bucket in enumerate(buckets):
                        cumulative += counts["bucket_counts"][i]
                        if label_str:
                            bucket_label = f'{label_str[:-1]},le="{bucket}"}}'
                        else:
                            bucket_label = f'{{le="{bucket}"}}'
                        lines.append(f"{name}_bucket{bucket_label} {cumulative}")

                    # +Inf bucket
                    if label_str:
                        inf_label = f'{label_str[:-1]},le="+Inf"}}'
                    else:
                        inf_label = f'{{le="+Inf"}}'
                    lines.append(f"{name}_bucket{inf_label} {counts['count']}")

                    # Sum 和 Count
                    lines.append(f"{name}_sum{label_str} {counts['sum']}")
                    lines.append(f"{name}_count{label_str} {counts['count']}")

            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def _extract_labels(self, key: str) -> dict[str, str]:
        """从键中提取标签"""
        if ":" not in key:
            return {}
        label_part = key.split(":")[1]
        labels = {}
        for pair in label_part.split(","):
            if "=" in pair:
                k, v = pair.split("=")
                labels[k] = v
        return labels

    def _format_labels(self, labels: dict[str, str]) -> str:
        """格式化标签"""
        if not labels:
            return ""
        pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(pairs) + "}"

    def clear(self) -> None:
        """清除所有值"""
        self._values.clear()
        self._counter_values.clear()
        self._gauge_values.clear()
        self._histogram_counts.clear()

        # 重新初始化值存储
        for name in self._metrics:
            self._values[name] = []

    def get_summary(self) -> dict[str, Any]:
        """获取指标摘要"""
        return {
            "total_metrics": len(self._metrics),
            "total_counter_values": len(self._counter_values),
            "total_gauge_values": len(self._gauge_values),
            "total_histogram_counts": len(self._histogram_counts),
            "metrics_by_type": {
                "counter": sum(1 for m in self._metrics.values() if m.type == MetricType.COUNTER),
                "gauge": sum(1 for m in self._metrics.values() if m.type == MetricType.GAUGE),
                "histogram": sum(1 for m in self._metrics.values() if m.type == MetricType.HISTOGRAM),
            },
        }


class MetricsCollector:
    """指标收集器

    从各个数据源收集指标并更新到 Registry。
    """

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self._registry = registry or get_metrics_registry()

    async def collect_patrol_metrics(self, patrol_results: dict[str, Any]) -> None:
        """收集 Patrol 指标"""
        for rule_name, result in patrol_results.items():
            status = result.get("status", "unknown")
            issues = result.get("issues", [])
            duration = result.get("duration_seconds", 0)
            timestamp = result.get("timestamp", time.time())

            # 计数
            self._registry.counter(
                "sre_patrol_total",
                labels={"status": status, "rule_name": rule_name},
            )

            # 时长
            self._registry.histogram(
                "sre_patrol_duration_seconds",
                value=duration,
                labels={"rule_name": rule_name},
            )

            # 问题数
            by_severity = {}
            for issue in issues:
                severity = issue.get("severity", "medium")
                by_severity[severity] = by_severity.get(severity, 0) + 1

            for severity, count in by_severity.items():
                self._registry.gauge(
                    "sre_patrol_issues_found",
                    value=count,
                    labels={"rule_name": rule_name, "severity": severity},
                )

            # 最后运行时间
            self._registry.gauge(
                "sre_patrol_last_run_timestamp",
                value=timestamp,
                labels={"rule_name": rule_name},
            )

    async def collect_spark_metrics(self, spark_apps: list[dict[str, Any]]) -> None:
        """收集 Spark 指标"""
        for app in spark_apps:
            app_id = app.get("id", "unknown")
            status = app.get("status", "unknown")
            user = app.get("spark_user", "unknown")
            duration = app.get("duration_ms", 0) / 1000.0
            failed_tasks = app.get("failed_tasks", 0)

            # 应用计数
            self._registry.gauge(
                "sre_spark_applications_total",
                value=1,
                labels={"status": status, "user": user},
            )

            # 时长
            if duration > 0:
                self._registry.histogram(
                    "sre_spark_application_duration_seconds",
                    value=duration,
                    labels={"status": status, "app_name": app.get("name", "unknown")},
                )

            # 失败任务
            if failed_tasks > 0:
                self._registry.gauge(
                    "sre_spark_application_failed_tasks",
                    value=failed_tasks,
                    labels={"app_id": app_id, "stage_id": "total"},
                )

    async def collect_yunikorn_metrics(self, queue_data: list[dict[str, Any]]) -> None:
        """收集 YuniKorn 指标"""
        for queue in queue_data:
            queue_name = queue.get("name", "unknown")

            # 应用计数
            for state, count in queue.get("applications", {}).items():
                self._registry.gauge(
                    "sre_yunikorn_queue_applications_total",
                    value=count,
                    labels={"queue_name": queue_name, "state": state},
                )

            # 内存
            memory_allocated = queue.get("memory_allocated", 0)
            memory_used = queue.get("memory_used", 0)
            self._registry.gauge(
                "sre_yunikorn_queue_memory_allocated_bytes",
                value=memory_allocated,
                labels={"queue_name": queue_name},
            )
            self._registry.gauge(
                "sre_yunikorn_queue_memory_used_bytes",
                value=memory_used,
                labels={"queue_name": queue_name},
            )

            # CPU
            cpu_allocated = queue.get("cpu_allocated", 0)
            cpu_used = queue.get("cpu_used", 0)
            self._registry.gauge(
                "sre_yunikorn_queue_cpu_allocated_cores",
                value=cpu_allocated,
                labels={"queue_name": queue_name},
            )
            self._registry.gauge(
                "sre_yunikorn_queue_cpu_used_cores",
                value=cpu_used,
                labels={"queue_name": queue_name},
            )

    async def collect_k8s_metrics(self, k8s_data: dict[str, Any]) -> None:
        """收集 Kubernetes 指标"""
        # Pod 计数
        for namespace, pods_by_status in k8s_data.get("pods", {}).items():
            for status, count in pods_by_status.items():
                self._registry.gauge(
                    "sre_k8s_pods_total",
                    value=count,
                    labels={"namespace": namespace, "status": status},
                )

        # Node 计数
        for status, count in k8s_data.get("nodes", {}).items():
            self._registry.gauge(
                "sre_k8s_nodes_total",
                value=count,
                labels={"status": status},
            )

        # Node 资源使用
        for node_name, usage in k8s_data.get("node_usage", {}).items():
            cpu_percent = usage.get("cpu_percent", 0)
            memory_percent = usage.get("memory_percent", 0)
            self._registry.gauge(
                "sre_k8s_node_cpu_usage_percent",
                value=cpu_percent,
                labels={"node_name": node_name},
            )
            self._registry.gauge(
                "sre_k8s_node_memory_usage_percent",
                value=memory_percent,
                labels={"node_name": node_name},
            )

    async def collect_agent_metrics(self, agent_data: dict[str, Any]) -> None:
        """收集 Agent 指标"""
        # 会话
        sessions = agent_data.get("sessions_total", 0)
        self._registry.counter("sre_agent_chat_sessions_total", value=sessions)

        # 消息
        messages = agent_data.get("messages_total", 0)
        self._registry.counter("sre_agent_chat_messages_total", value=messages)

        # 工具调用
        for tool_name, tool_stats in agent_data.get("tool_calls", {}).items():
            for status, count in tool_stats.items():
                self._registry.counter(
                    "sre_agent_tool_calls_total",
                    value=count,
                    labels={"tool_name": tool_name, "status": status},
                )

        # LLM tokens
        input_tokens = agent_data.get("llm_tokens_input", 0)
        output_tokens = agent_data.get("llm_tokens_output", 0)
        self._registry.counter(
            "sre_agent_llm_tokens_total",
            value=input_tokens,
            labels={"type": "input"},
        )
        self._registry.counter(
            "sre_agent_llm_tokens_total",
            value=output_tokens,
            labels={"type": "output"},
        )


# 全局实例
_metrics_registry: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    """获取全局指标注册表"""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器"""
    return MetricsCollector(get_metrics_registry())