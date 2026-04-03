"""Kubernetes 工具实现"""

from typing import Any

from pydantic import BaseModel
from structlog import get_logger

from app.agent.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
)
from app.infrastructure.k8s_client import get_k8s_client

logger = get_logger()


class K8sPodListArgs(BaseModel):
    """Pod 列表参数"""
    namespace: str | None = None
    label_selector: str | None = None
    status: str | None = None


class K8sPodGetArgs(BaseModel):
    """Pod 详情参数"""
    name: str
    namespace: str = "default"


class K8sPodLogsArgs(BaseModel):
    """Pod 日志参数"""
    name: str
    namespace: str = "default"
    container: str | None = None
    tail_lines: int = 500


class K8sPodDeleteArgs(BaseModel):
    """Pod 删除参数"""
    name: str
    namespace: str = "default"


class K8sNodeListArgs(BaseModel):
    """Node 列表参数"""
    label_selector: str | None = None
    status: str | None = None


class K8sNodeGetArgs(BaseModel):
    """Node 详情参数"""
    name: str


class K8sPodListTool(BaseTool):
    """K8s Pod 列表查询"""

    name = "k8s_pod_list"
    description = "查询 Kubernetes Pod 列表"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE
    args_schema = K8sPodListArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = K8sPodListArgs(**args).model_dump()

        k8s = get_k8s_client()

        # 构造 field_selector
        field_selector = None
        if kwargs.get("status"):
            field_selector = f"status.phase={kwargs['status']}"

        pods = k8s.list_pods(
            namespace=kwargs.get("namespace"),
            label_selector=kwargs.get("label_selector"),
            field_selector=field_selector,
        )

        return {
            "success": True,
            "pods": pods,
            "total": len(pods),
            "query": kwargs,
        }


class K8sPodGetTool(BaseTool):
    """K8s Pod 详情查询"""

    name = "k8s_pod_get"
    description = "获取单个 Pod 的详细信息"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE
    args_schema = K8sPodGetArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = K8sPodGetArgs(**args).model_dump()

        k8s = get_k8s_client()
        pod = k8s.get_pod(kwargs["name"], kwargs["namespace"])

        if not pod:
            return {
                "success": False,
                "error": f"Pod 不存在: {kwargs['name']}",
            }

        return {
            "success": True,
            "pod": pod,
        }


class K8sPodLogsTool(BaseTool):
    """K8s Pod 日志获取"""

    name = "k8s_pod_logs"
    description = "获取 Pod 日志"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE
    args_schema = K8sPodLogsArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = K8sPodLogsArgs(**args).model_dump()

        k8s = get_k8s_client()
        logs = k8s.get_pod_logs(
            kwargs["name"],
            kwargs["namespace"],
            kwargs.get("container"),
            kwargs["tail_lines"],
        )

        return {
            "success": True,
            "logs": logs,
            "pod_name": kwargs["name"],
            "namespace": kwargs["namespace"],
        }


class K8sPodDeleteTool(BaseTool):
    """K8s Pod 删除（高风险）"""

    name = "k8s_pod_delete"
    description = "删除 Pod（高风险操作，需要审批）"
    category = ToolCategory.K8S
    risk_level = RiskLevel.HIGH
    args_schema = K8sPodDeleteArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行删除"""
        kwargs = K8sPodDeleteArgs(**args).model_dump()

        logger.warning(
            "pod_delete_requested",
            name=kwargs["name"],
            namespace=kwargs["namespace"],
        )

        k8s = get_k8s_client()
        success = k8s.delete_pod(kwargs["name"], kwargs["namespace"])

        return {
            "success": success,
            "action": "delete",
            "resource": f"Pod/{kwargs['namespace']}/{kwargs['name']}",
        }


class K8sNodeListTool(BaseTool):
    """K8s Node 列表查询"""

    name = "k8s_node_list"
    description = "查询 Kubernetes Node 列表"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE
    args_schema = K8sNodeListArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = K8sNodeListArgs(**args).model_dump()

        k8s = get_k8s_client()
        nodes = k8s.list_nodes(kwargs.get("label_selector"))

        # 状态过滤
        if kwargs.get("status"):
            nodes = [n for n in nodes if n.get("status") == kwargs["status"]]

        return {
            "success": True,
            "nodes": nodes,
            "total": len(nodes),
        }


class K8sNodeGetTool(BaseTool):
    """K8s Node 详情查询"""

    name = "k8s_node_get"
    description = "获取单个 Node 的详细信息"
    category = ToolCategory.K8S
    risk_level = RiskLevel.SAFE
    args_schema = K8sNodeGetArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = K8sNodeGetArgs(**args).model_dump()

        k8s = get_k8s_client()
        node = k8s.get_node(kwargs["name"])

        if not node:
            return {
                "success": False,
                "error": f"Node 不存在: {kwargs['name']}",
            }

        return {
            "success": True,
            "node": node,
        }