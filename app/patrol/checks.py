"""巡检检查实现"""

from typing import Any
from datetime import datetime, timedelta

from structlog import get_logger

from app.patrol.engine import BaseCheck, CheckResult
from app.infrastructure.k8s_client import get_k8s_client
from app.infrastructure.yunikorn_client import get_yunikorn_client

logger = get_logger()


class SparkFailureCheck(BaseCheck):
    """Spark 任务失败检查"""

    name = "spark_failures"
    description = "检查最近失败的 Spark 任务"
    enabled = True

    # 配置
    failure_threshold = 3  # 触发警告的失败数量
    time_window_hours = 1  # 时间窗口（小时）

    async def execute(self) -> CheckResult:
        """执行检查"""
        k8s = get_k8s_client()

        # 获取 Spark 应用列表
        apps = k8s.list_spark_applications()

        # 统计失败应用
        failed_apps = [
            app for app in apps
            if app.get("status") in ["FAILED", "COMPLETED"] and "error" in app.get("error_message", "").lower()
        ]

        # 按错误类型分组
        error_groups: dict[str, list[dict[str, Any]]] = {}
        for app in failed_apps:
            error_msg = app.get("error_message", "unknown")
            error_type = self._classify_error(error_msg)
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(app)

        # 判断状态
        if len(failed_apps) == 0:
            return self._pass(
                message="没有发现失败的 Spark 任务",
                details={"failed_count": 0},
            )

        if len(failed_apps) >= self.failure_threshold:
            return self._error(
                message=f"发现 {len(failed_apps)} 个失败的 Spark 任务",
                details={
                    "failed_count": len(failed_apps),
                    "error_breakdown": {
                        error_type: len(apps)
                        for error_type, apps in error_groups.items()
                    },
                    "recent_failures": [
                        {"name": a.get("name"), "error": a.get("error_message")}
                        for a in failed_apps[:5]
                    ],
                },
                suggestions=self._generate_suggestions(error_groups),
            )

        return self._warning(
            message=f"发现 {len(failed_apps)} 个失败的 Spark 任务",
            details={
                "failed_count": len(failed_apps),
                "recent_failures": [
                    {"name": a.get("name"), "error": a.get("error_message")}
                    for a in failed_apps[:5]
                ],
            },
            suggestions=["检查失败任务日志", "确认是否有资源不足或配置问题"],
        )

    def _classify_error(self, error_message: str) -> str:
        """分类错误类型"""
        error_lower = error_message.lower()
        if "oom" in error_lower or "out of memory" in error_lower:
            return "OOM"
        if "timeout" in error_lower:
            return "TIMEOUT"
        if "connection" in error_lower or "network" in error_lower:
            return "NETWORK"
        if "classnotfound" in error_lower:
            return "CLASS_NOT_FOUND"
        return "UNKNOWN"

    def _generate_suggestions(self, error_groups: dict[str, list]) -> list[str]:
        """生成建议"""
        suggestions = []

        if "OOM" in error_groups:
            suggestions.append("OOM 错误: 检查 Executor 内存配置，考虑增加内存或优化数据倾斜")
        if "TIMEOUT" in error_groups:
            suggestions.append("超时错误: 检查任务执行时间，增加超时配置或优化任务")
        if "NETWORK" in error_groups:
            suggestions.append("网络错误: 检查网络连通性和带宽")
        if "CLASS_NOT_FOUND" in error_groups:
            suggestions.append("类未找到: 检查依赖配置和 Jar 包路径")

        return suggestions


class QueueUtilizationCheck(BaseCheck):
    """YuniKorn 队列利用率检查"""

    name = "queue_utilization"
    description = "检查队列资源利用率"
    enabled = True

    # 配置
    warning_threshold = 70  # 警告阈值
    critical_threshold = 90  # 严重阈值

    async def execute(self) -> CheckResult:
        """执行检查"""
        yunikorn = get_yunikorn_client()

        # 获取队列列表
        queues = yunikorn.list_queues()

        # 检查每个队列
        critical_queues = []
        warning_queues = []

        for queue in queues:
            # 计算利用率
            used = queue.get("used_capacity", {})
            max_cap = queue.get("max_capacity", {})

            if not used or not max_cap:
                continue

            # 简单计算（基于 vcore）
            used_vcore = self._parse_resource(used.get("vcore", 0))
            max_vcore = self._parse_resource(max_cap.get("vcore", 0))

            if max_vcore == 0:
                continue

            utilization = (used_vcore / max_vcore) * 100

            queue_info = {
                "name": queue.get("name"),
                "utilization": f"{utilization:.1f}%",
                "used": used,
                "max": max_cap,
                "pending_apps": queue.get("pending_apps", 0),
            }

            if utilization >= self.critical_threshold:
                critical_queues.append(queue_info)
            elif utilization >= self.warning_threshold:
                warning_queues.append(queue_info)

        # 判断状态
        if critical_queues:
            return self._critical(
                message=f"发现 {len(critical_queues)} 个队列利用率超过 {self.critical_threshold}%",
                details={
                    "critical_queues": critical_queues,
                    "warning_queues": warning_queues,
                },
                suggestions=[
                    "紧急: 扩容集群资源或调整队列配额",
                    "检查是否有资源泄露",
                    "考虑暂停低优先级任务",
                ],
            )

        if warning_queues:
            return self._warning(
                message=f"发现 {len(warning_queues)} 个队列利用率超过 {self.warning_threshold}%",
                details={
                    "warning_queues": warning_queues,
                },
                suggestions=[
                    "关注资源使用趋势",
                    "考虑扩容或调整配额",
                ],
            )

        return self._pass(
            message="所有队列资源利用率正常",
            details={
                "total_queues": len(queues),
                "max_utilization": max(
                    [self._get_queue_utilization(q) for q in queues] + [0]
                ),
            },
        )

    def _parse_resource(self, value: Any) -> int:
        """解析资源值"""
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            # 移除单位
            value = value.replace("Gi", "").replace("Mi", "").replace("vcore", "")
            try:
                return int(float(value))
            except ValueError:
                return 0
        return 0

    def _get_queue_utilization(self, queue: dict) -> float:
        """获取队列利用率"""
        used = queue.get("used_capacity", {})
        max_cap = queue.get("max_capacity", {})
        used_vcore = self._parse_resource(used.get("vcore", 0))
        max_vcore = self._parse_resource(max_cap.get("vcore", 0))
        if max_vcore == 0:
            return 0
        return (used_vcore / max_vcore) * 100


class NodeHealthCheck(BaseCheck):
    """K8s 节点健康检查"""

    name = "node_health"
    description = "检查 Kubernetes 节点健康状态"
    enabled = True

    async def execute(self) -> CheckResult:
        """执行检查"""
        k8s = get_k8s_client()

        # 获取节点列表
        nodes = k8s.list_nodes()

        # 统计
        ready_nodes = []
        not_ready_nodes = []

        for node in nodes:
            node_name = node.get("name", "")
            status = node.get("status", "Unknown")

            if status == "Ready":
                ready_nodes.append(node_name)
            else:
                not_ready_nodes.append({
                    "name": node_name,
                    "status": status,
                    "conditions": node.get("conditions", {}),
                })

        # 判断状态
        total_nodes = len(nodes)
        ready_count = len(ready_nodes)

        if ready_count == 0:
            return self._critical(
                message="所有节点都不可用",
                details={
                    "total_nodes": total_nodes,
                    "not_ready_nodes": not_ready_nodes,
                },
                suggestions=["紧急检查集群状态", "检查网络和 kubelet 服务"],
            )

        if not_ready_nodes:
            return self._warning(
                message=f"发现 {len(not_ready_nodes)} 个节点不健康",
                details={
                    "total_nodes": total_nodes,
                    "ready_nodes": ready_count,
                    "not_ready_nodes": not_ready_nodes,
                },
                suggestions=[
                    "检查节点资源使用情况",
                    "检查 kubelet 和容器运行时状态",
                ],
            )

        return self._pass(
            message=f"所有 {total_nodes} 个节点运行正常",
            details={
                "total_nodes": total_nodes,
                "ready_nodes": ready_nodes,
            },
        )


class PodRestartCheck(BaseCheck):
    """Pod 重启检查"""

    name = "pod_restarts"
    description = "检查频繁重启的 Pod"
    enabled = True

    # 配置
    restart_threshold = 5  # 重启次数阈值

    async def execute(self) -> CheckResult:
        """执行检查"""
        k8s = get_k8s_client()

        # 获取 Pod 列表
        pods = k8s.list_pods()

        # 检查重启次数（Mock 数据不包含重启信息，这里做简化处理）
        high_restart_pods = []

        # 实际环境应该检查 pod.status.containerStatuses[*].restartCount
        # 这里简化为检查状态为 Failed 的 Pod
        failed_pods = [
            pod for pod in pods
            if pod.get("status") in ["Failed", "Error", "CrashLoopBackOff"]
        ]

        for pod in failed_pods:
            high_restart_pods.append({
                "name": pod.get("name"),
                "namespace": pod.get("namespace"),
                "status": pod.get("status"),
            })

        # 判断状态
        if not high_restart_pods:
            return self._pass(
                message="没有发现频繁重启的 Pod",
                details={"checked_pods": len(pods)},
            )

        if len(high_restart_pods) >= 5:
            return self._error(
                message=f"发现 {len(high_restart_pods)} 个异常 Pod",
                details={
                    "high_restart_pods": high_restart_pods[:10],
                },
                suggestions=[
                    "检查 Pod 日志定位错误原因",
                    "检查资源限制配置",
                    "检查健康检查配置",
                ],
            )

        return self._warning(
            message=f"发现 {len(high_restart_pods)} 个异常 Pod",
            details={
                "high_restart_pods": high_restart_pods,
            },
            suggestions=["检查 Pod 日志", "确认是否需要调整资源"],
        )


def get_default_checks() -> list[BaseCheck]:
    """获取默认检查列表"""
    return [
        SparkFailureCheck(),
        QueueUtilizationCheck(),
        NodeHealthCheck(),
        PodRestartCheck(),
    ]