"""Spark 工具实现"""

import re
from typing import Any

from structlog import get_logger

from app.agent.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
)
from app.infrastructure.k8s_client import get_k8s_client

logger = get_logger()


# 错误模式定义
ERROR_PATTERNS = [
    {
        "id": "OOM_DRIVER",
        "name": "Driver 内存溢出",
        "patterns": [
            r"java\.lang\.OutOfMemoryError",
            r"Container killed.*exceeding memory",
            r"Memory limit exceeded",
        ],
        "severity": "high",
        "root_cause": "Driver 内存不足",
        "suggestions": [
            "增加 spark.driver.memory 配置",
            "检查是否有数据倾斜（collect() 大数据集）",
            "优化代码减少 Driver 内存占用",
        ],
    },
    {
        "id": "OOM_EXECUTOR",
        "name": "Executor 内存溢出",
        "patterns": [
            r"ExecutorLostFailure.*OOM",
            r"java\.lang\.OutOfMemoryError: Java heap space",
            r"Container.*exceeded memory",
        ],
        "severity": "high",
        "root_cause": "Executor 内存不足",
        "suggestions": [
            "增加 spark.executor.memory 配置",
            "减少 spark.executor.cores（降低并行度）",
            "增加 spark.executor.instances（分担压力）",
            "检查是否有数据倾斜",
        ],
    },
    {
        "id": "SHUFFLE_ERROR",
        "name": "Shuffle 失败",
        "patterns": [
            r"FetchFailedException",
            r"Failed to fetch.*shuffle",
            r"Connection refused.*shuffle",
        ],
        "severity": "high",
        "root_cause": "Shuffle 数据传输失败",
        "suggestions": [
            "检查网络连通性",
            "增加 spark.shuffle.io.maxRetries",
            "检查是否有 Executor 频繁丢失",
        ],
    },
    {
        "id": "EXECUTOR_LOST",
        "name": "Executor 丢失",
        "patterns": [
            r"ExecutorLostFailure",
            r"Executor.*lost",
            r"Container.*exit",
        ],
        "severity": "medium",
        "root_cause": "Executor 进程异常退出",
        "suggestions": [
            "检查 Executor 资源配置",
            "查看 Executor 日志确定原因",
            "检查是否有外部 kill 信号",
        ],
    },
    {
        "id": "CLASS_NOT_FOUND",
        "name": "类未找到",
        "patterns": [
            r"ClassNotFoundException",
            r"NoClassDefFoundError",
            r"Class not found",
        ],
        "severity": "low",
        "root_cause": "依赖缺失或配置错误",
        "suggestions": [
            "检查 spark.jars 或 spark.sql.jar.packages 配置",
            "确认依赖包已正确上传",
            "检查 Main Class 名称是否正确",
        ],
    },
]


class SparkListTool(BaseTool):
    """Spark 应用列表查询"""

    name = "spark_list"
    description = "查询 Spark 应用列表，支持按状态、命名空间过滤"
    category = ToolCategory.SPARK
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        namespace = args.get("namespace")
        status = args.get("status")  # list[str] or str
        limit = args.get("limit", 50)

        logger.info(
            "spark_list_query",
            namespace=namespace,
            status=status,
            limit=limit,
        )

        # 使用 K8s 客户端查询 Spark Application CRD
        k8s = get_k8s_client()
        applications = k8s.list_spark_applications(namespace)

        # 过滤状态
        if status:
            if isinstance(status, str):
                status = [status]
            applications = [
                a for a in applications
                if a.get("status") in status or a.get("status") in [s.upper() for s in status]
            ]

        # 截断
        applications = applications[:limit]

        return {
            "applications": applications,
            "total": len(applications),
            "query": {
                "namespace": namespace,
                "status": status,
                "limit": limit,
            },
        }


class SparkGetTool(BaseTool):
    """Spark 应用详情查询"""

    name = "spark_get"
    description = "获取单个 Spark 应用的详细信息"
    category = ToolCategory.SPARK
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        app_name = args.get("app_name", "")
        namespace = args.get("namespace", "default")

        logger.info("spark_get_query", app_name=app_name, namespace=namespace)

        if not app_name:
            return {"error": "缺少 app_name 参数"}

        # 使用 K8s 客户端查询
        k8s = get_k8s_client()
        app = k8s.get_spark_application(app_name, namespace)

        if not app:
            return {"error": f"应用不存在: {app_name} (namespace: {namespace})"}

        # 添加详细信息
        app_detail = {
            **app,
            "spec": {
                "driver_cores": 2,
                "driver_memory": "4g",
                "executor_cores": 4,
                "executor_memory": "8g",
                "executor_instances": 3,
            },
        }

        return {
            "application": app_detail,
            "app_name": app_name,
        }


class SparkLogsTool(BaseTool):
    """Spark 日志获取"""

    name = "spark_logs"
    description = "获取 Spark Pod 日志"
    category = ToolCategory.SPARK
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        app_name = args.get("app_name", "")
        pod_type = args.get("pod_type", "driver")  # driver / executor
        namespace = args.get("namespace", "default")
        tail_lines = args.get("tail_lines", 500)

        logger.info(
            "spark_logs_query",
            app_name=app_name,
            pod_type=pod_type,
            namespace=namespace,
        )

        if not app_name:
            return {"error": "缺少 app_name 参数"}

        # 构造 Pod 名称
        pod_name = f"{app_name}-driver" if pod_type == "driver" else f"{app_name}-executor-1"

        # 使用 K8s 客户端获取日志
        k8s = get_k8s_client()
        logs = k8s.get_pod_logs(pod_name, namespace, tail_lines=tail_lines)

        return {
            "logs": logs,
            "pod_name": pod_name,
            "pod_type": pod_type,
            "namespace": namespace,
            "tail_lines": tail_lines,
        }


class SparkAnalyzeTool(BaseTool):
    """Spark 日志分析"""

    name = "spark_analyze"
    description = "分析 Spark 日志，诊断问题原因"
    category = ToolCategory.ANALYSIS
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行分析"""
        logs = args.get("logs", "")
        app_name = args.get("app_name", "")
        recent_failures = args.get("recent_failures")

        logger.info("spark_analyze", app_name=app_name)

        if recent_failures:
            # 分析批量失败
            return self._analyze_failures(recent_failures)

        if not logs and app_name:
            # 如果没有日志，先获取
            logs_tool = SparkLogsTool()
            result = logs_tool.execute({"app_name": app_name, "pod_type": "driver"})
            if "error" in result:
                return result
            logs = result.get("logs", "")

        # 匹配错误模式
        issues = self._match_error_patterns(logs)

        # 推断根因
        root_cause = self._infer_root_cause(issues)

        # 生成建议
        recommendations = self._generate_recommendations(issues)

        return {
            "app_name": app_name,
            "issues": issues,
            "root_cause": root_cause,
            "recommendations": recommendations,
            "analysis_status": "completed" if issues else "no_issues_found",
        }

    def _match_error_patterns(self, logs: str) -> list[dict[str, Any]]:
        """匹配错误模式"""
        issues = []

        for pattern_def in ERROR_PATTERNS:
            for pattern in pattern_def["patterns"]:
                matches = re.findall(pattern, logs, re.IGNORECASE)
                if matches:
                    # 提取上下文
                    context = self._extract_context(logs, str(matches[0]))

                    issues.append({
                        "severity": pattern_def["severity"],
                        "type": pattern_def["id"],
                        "description": pattern_def["name"],
                        "evidence": context,
                        "root_cause": pattern_def["root_cause"],
                        "suggestions": pattern_def["suggestions"],
                    })
                    break  # 匹配到一个模式后跳出

        return issues

    def _extract_context(self, logs: str, match_text: str) -> str:
        """提取错误上下文"""
        lines = logs.split("\n")
        context_lines = []

        for i, line in enumerate(lines):
            if match_text in line:
                # 取前后 3 行
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                context_lines = lines[start:end]
                break

        return "\n".join(context_lines)

    def _infer_root_cause(self, issues: list[dict[str, Any]]) -> str | None:
        """推断根因"""
        if not issues:
            return None

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(x["severity"], 3)
        )

        return sorted_issues[0].get("root_cause")

    def _generate_recommendations(
        self, issues: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """生成建议"""
        recommendations = []

        for issue in issues:
            for i, suggestion in enumerate(issue.get("suggestions", [])):
                recommendations.append({
                    "priority": i + 1,
                    "action": suggestion,
                    "reason": issue.get("root_cause", ""),
                    "severity": issue.get("severity", "medium"),
                })

        return recommendations

    def _analyze_failures(self, failures: dict[str, Any]) -> dict[str, Any]:
        """分析批量失败"""
        applications = failures.get("applications", [])

        if not applications:
            return {
                "analysis_status": "no_failures_found",
                "issues": [],
                "root_cause": None,
                "recommendations": [],
            }

        # 统计失败类型
        error_types = {}
        for app in applications:
            error_msg = app.get("error_message", "unknown")
            error_types[error_msg] = error_types.get(error_msg, 0) + 1

        # 提取主要失败原因
        main_error = max(error_types.items(), key=lambda x: x[1])[0]

        issues = [{
            "severity": "high",
            "type": "batch_failure_pattern",
            "description": f"发现 {len(applications)} 个失败任务",
            "evidence": f"主要错误: {main_error} ({error_types[main_error]} 次)",
            "root_cause": main_error,
            "suggestions": [
                "检查集群资源是否充足",
                "检查是否有配置变更",
                "检查数据源是否正常",
            ],
        }]

        return {
            "analysis_status": "completed",
            "total_failures": len(applications),
            "error_distribution": error_types,
            "issues": issues,
            "root_cause": main_error,
            "recommendations": issues[0]["suggestions"],
        }
