"""Kubernetes 工具实现"""

from typing import Any

from structlog import get_logger

from app.agent.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
    _mock_k8s_nodes,
    _mock_k8s_pods,
)

logger = get_logger()


class K8sPodListTool(BaseTool):
    """K8s Pod 列表查询"""

    name = "k8s_pod_list"
    description = "查询 Kubernetes Pod 列表"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        namespace = args.get("namespace")
        status = args.get("status")  # Running / Succeeded / Failed / Pending
        label_selector = args.get("label_selector")
        limit = args.get("limit", 100)

        logger.info(
            "k8s_pod_list",
            namespace=namespace,
            status=status,
            label_selector=label_selector,
        )

        # Mock 数据
        pods = _mock_k8s_pods()

        # 过滤
        if namespace:
            pods = [p for p in pods if p["namespace"] == namespace]

        if status:
            pods = [p for p in pods if p["status"] == status]

        # 截断
        pods = pods[:limit]

        return {
            "pods": pods,
            "total": len(pods),
            "query": {
                "namespace": namespace,
                "status": status,
                "label_selector": label_selector,
            },
        }


class K8sPodGetTool(BaseTool):
    """K8s Pod 详情查询"""

    name = "k8s_pod_get"
    description = "获取单个 Pod 的详细信息"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        pod_name = args.get("pod_name", "")
        namespace = args.get("namespace", "default")

        logger.info("k8s_pod_get", pod_name=pod_name, namespace=namespace)

        if not pod_name:
            return {"error": "缺少 pod_name 参数"}

        # Mock 数据
        pods = _mock_k8s_pods()

        # 查找 Pod
        pod = None
        for p in pods:
            if p["name"] == pod_name and p["namespace"] == namespace:
                pod = p
                break

        if not pod:
            return {"error": f"Pod 不存在: {pod_name} (namespace: {namespace})"}

        # 添加详细信息
        pod_detail = {
            **pod,
            "spec": {
                "containers": [
                    {
                        "name": c,
                        "image": "spark-image:v3.1.1",
                        "resources": {
                            "requests": {"cpu": "1", "memory": "4Gi"},
                            "limits": {"cpu": "2", "memory": "8Gi"},
                        },
                    }
                    for c in pod["containers"]
                ],
                "node_name": pod["node"],
                "restart_policy": "Never",
            },
            "events": [
                {
                    "type": "Normal" if pod["status"] != "Failed" else "Warning",
                    "reason": "Started" if pod["status"] == "Running" else pod.get("error_reason", "Completed"),
                    "message": f"Container {pod['containers'][0]} started",
                    "timestamp": "2026-04-03T10:00:00Z",
                },
            ],
        }

        return {
            "pod": pod_detail,
            "pod_name": pod_name,
        }


class K8sPodDeleteTool(BaseTool):
    """K8s Pod 删除"""

    name = "k8s_pod_delete"
    description = "删除指定的 Pod（高风险操作）"
    category = ToolCategory.K8S
    risk_level = RiskLevel.HIGH

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行删除"""
        pod_name = args.get("pod_name", "")
        namespace = args.get("namespace", "default")
        force = args.get("force", False)

        logger.warning(
            "k8s_pod_delete_request",
            pod_name=pod_name,
            namespace=namespace,
            force=force,
        )

        if not pod_name:
            return {"error": "缺少 pod_name 参数"}

        # Mock 删除操作
        # 实际实现应调用 K8s API
        return {
            "deleted": True,
            "pod_name": pod_name,
            "namespace": namespace,
            "message": f"Pod {pod_name} 已删除",
            "warning": "这是一个高风险操作，已记录日志",
        }


class K8sNodeListTool(BaseTool):
    """K8s Node 列表查询"""

    name = "k8s_node_list"
    description = "查询 Kubernetes Node 列表"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        status = args.get("status")  # Ready / NotReady

        logger.info("k8s_node_list", status=status)

        # Mock 数据
        nodes = _mock_k8s_nodes()

        # 过滤
        if status:
            nodes = [n for n in nodes if n["status"] == status]

        return {
            "nodes": nodes,
            "total": len(nodes),
            "query": {"status": status},
        }


class K8sNodeGetTool(BaseTool):
    """K8s Node 详情查询"""

    name = "k8s_node_get"
    description = "获取单个 Node 的详细信息"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        node_name = args.get("node_name", "")

        logger.info("k8s_node_get", node_name=node_name)

        if not node_name:
            return {"error": "缺少 node_name 参数"}

        # Mock 数据
        nodes = _mock_k8s_nodes()

        # 查找 Node
        node = None
        for n in nodes:
            if n["name"] == node_name:
                node = n
                break

        if not node:
            return {"error": f"Node 不存在: {node_name}"}

        # 添加详细信息
        node_detail = {
            **node,
            "labels": {
                "kubernetes.io/arch": "amd64",
                "kubernetes.io/os": "linux",
                "node-role.kubernetes.io/worker": "true",
            },
            "addresses": [
                {"type": "InternalIP", "address": f"10.0.0.{node_name[-1]}"},
                {"type": "Hostname", "address": node_name},
            ],
            "conditions": [
                {
                    "type": "Ready",
                    "status": node["status"],
                    "reason": node.get("error_reason", "NodeReady"),
                    "message": f"Node {node_name} is {node['status']}",
                },
            ],
        }

        return {
            "node": node_detail,
            "node_name": node_name,
        }


class K8sPodLogsTool(BaseTool):
    """K8s Pod 日志查询"""

    name = "k8s_pod_logs"
    description = "获取 Pod 日志"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        pod_name = args.get("pod_name", "")
        namespace = args.get("namespace", "default")
        container = args.get("container")
        tail_lines = args.get("tail_lines", 100)

        logger.info(
            "k8s_pod_logs",
            pod_name=pod_name,
            container=container,
        )

        if not pod_name:
            return {"error": "缺少 pod_name 参数"}

        # Mock 日志
        logs = f"""
[2026-04-03 10:00:00] INFO: Starting container {container or 'main'}
[2026-04-03 10:00:05] INFO: Initialization complete
[2026-04-03 10:00:10] INFO: Application started
[2026-04-03 10:05:00] INFO: Processing task 1
[2026-04-03 10:10:00] INFO: Processing task 2
[2026-04-03 10:15:00] INFO: Task completed successfully
"""

        return {
            "logs": logs[:tail_lines * 100],
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container,
        }
