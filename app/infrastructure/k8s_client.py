"""Kubernetes 客户端封装"""

from typing import Any, Optional
from functools import lru_cache

from structlog import get_logger

logger = get_logger()

# K8s 客户端（可选依赖）
try:
    from kubernetes import client, config
    from kubernetes.client import (
        CoreV1Api,
        CustomObjectsApi,
        V1Pod,
        V1PodList,
        V1ConfigMap,
    )
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    logger.warning("kubernetes_not_available", note="Using mock data")


class K8sClient:
    """Kubernetes 客户端封装"""

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._core_v1: Optional[Any] = None
        self._custom_objects: Optional[Any] = None
        self._initialized = False

    def _init_client(self) -> None:
        """延迟初始化 K8s 客户端"""
        if self._initialized:
            return

        if not KUBERNETES_AVAILABLE:
            logger.warning("k8s_client_unavailable", fallback="mock_mode")
            self._initialized = True
            return

        try:
            # 尝试集群内配置
            try:
                config.load_incluster_config()
                logger.info("k8s_incluster_config_loaded")
            except config.ConfigException:
                # 尝试 kubeconfig
                config.load_kube_config()
                logger.info("k8s_kubeconfig_loaded")

            self._core_v1 = client.CoreV1Api()
            self._custom_objects = client.CustomObjectsApi()
            self._initialized = True

        except Exception as e:
            logger.error("k8s_client_init_failed", error=str(e))
            self._initialized = True

    @property
    def core_v1(self) -> Any:
        """获取 CoreV1 API"""
        self._init_client()
        return self._core_v1

    @property
    def custom_objects(self) -> Any:
        """获取 CustomObjects API"""
        self._init_client()
        return self._custom_objects

    @property
    def is_available(self) -> bool:
        """检查 K8s 是否可用"""
        self._init_client()
        return self._core_v1 is not None

    # ============ Pod 操作 ============

    def list_pods(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """列出 Pod"""
        ns = namespace or self.namespace

        if not self.is_available:
            return self._mock_pods(ns)

        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=ns,
                label_selector=label_selector,
                field_selector=field_selector,
            )
            return [self._pod_to_dict(pod) for pod in pods.items]
        except Exception as e:
            logger.error("list_pods_failed", error=str(e), namespace=ns)
            return []

    def get_pod(self, name: str, namespace: Optional[str] = None) -> dict[str, Any] | None:
        """获取 Pod 详情"""
        ns = namespace or self.namespace

        if not self.is_available:
            return self._mock_pod(name, ns)

        try:
            pod = self.core_v1.read_namespaced_pod(name=name, namespace=ns)
            return self._pod_to_dict(pod)
        except Exception as e:
            logger.error("get_pod_failed", error=str(e), name=name, namespace=ns)
            return None

    def get_pod_logs(
        self,
        name: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        tail_lines: int = 500,
    ) -> str:
        """获取 Pod 日志"""
        ns = namespace or self.namespace

        if not self.is_available:
            return self._mock_logs(name)

        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=name,
                namespace=ns,
                container=container,
                tail_lines=tail_lines,
            )
            return logs
        except Exception as e:
            logger.error("get_pod_logs_failed", error=str(e), name=name, namespace=ns)
            return f"Error getting logs: {e}"

    def delete_pod(self, name: str, namespace: Optional[str] = None) -> bool:
        """删除 Pod"""
        ns = namespace or self.namespace

        if not self.is_available:
            logger.warning("delete_pod_mock", name=name, namespace=ns)
            return True

        try:
            self.core_v1.delete_namespaced_pod(name=name, namespace=ns)
            logger.info("pod_deleted", name=name, namespace=ns)
            return True
        except Exception as e:
            logger.error("delete_pod_failed", error=str(e), name=name, namespace=ns)
            return False

    # ============ Node 操作 ============

    def list_nodes(self, label_selector: Optional[str] = None) -> list[dict[str, Any]]:
        """列出 Node"""
        if not self.is_available:
            return self._mock_nodes()

        try:
            nodes = self.core_v1.list_node(label_selector=label_selector)
            return [self._node_to_dict(node) for node in nodes.items]
        except Exception as e:
            logger.error("list_nodes_failed", error=str(e))
            return []

    def get_node(self, name: str) -> dict[str, Any] | None:
        """获取 Node 详情"""
        if not self.is_available:
            return self._mock_node(name)

        try:
            node = self.core_v1.read_node(name=name)
            return self._node_to_dict(node)
        except Exception as e:
            logger.error("get_node_failed", error=str(e), name=name)
            return None

    # ============ Spark Application CRD 操作 ============

    SPARK_GROUP = "sparkoperator.k8s.io"
    SPARK_VERSION = "v1beta2"
    SPARK_PLURAL = "sparkapplications"

    def list_spark_applications(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """列出 Spark Application"""
        ns = namespace or self.namespace

        if not self.is_available:
            return self._mock_spark_apps(ns)

        try:
            apps = self.custom_objects.list_namespaced_custom_object(
                group=self.SPARK_GROUP,
                version=self.SPARK_VERSION,
                namespace=ns,
                plural=self.SPARK_PLURAL,
                label_selector=label_selector,
            )
            return [self._spark_app_to_dict(app) for app in apps.get("items", [])]
        except Exception as e:
            logger.error("list_spark_apps_failed", error=str(e), namespace=ns)
            return self._mock_spark_apps(ns)

    def get_spark_application(
        self,
        name: str,
        namespace: Optional[str] = None,
    ) -> dict[str, Any] | None:
        """获取 Spark Application 详情"""
        ns = namespace or self.namespace

        if not self.is_available:
            return self._mock_spark_app(name, ns)

        try:
            app = self.custom_objects.get_namespaced_custom_object(
                group=self.SPARK_GROUP,
                version=self.SPARK_VERSION,
                namespace=ns,
                plural=self.SPARK_PLURAL,
                name=name,
            )
            return self._spark_app_to_dict(app)
        except Exception as e:
            logger.error("get_spark_app_failed", error=str(e), name=name, namespace=ns)
            return None

    # ============ 辅助方法 ============

    def _pod_to_dict(self, pod: Any) -> dict[str, Any]:
        """转换 Pod 为字典"""
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "pod_ip": pod.status.pod_ip,
            "node_name": pod.spec.node_name,
            "labels": pod.metadata.labels or {},
            "containers": [
                {"name": c.name, "image": c.image}
                for c in pod.spec.containers
            ],
            "created_at": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
        }

    def _node_to_dict(self, node: Any) -> dict[str, Any]:
        """转换 Node 为字典"""
        conditions = {c.type: c.status for c in (node.status.conditions or [])}
        return {
            "name": node.metadata.name,
            "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
            "roles": self._get_node_roles(node.metadata.labels or {}),
            "addresses": [
                {"type": addr.type, "address": addr.address}
                for addr in (node.status.addresses or [])
            ],
            "allocatable": dict(node.status.allocatable) if node.status.allocatable else {},
            "conditions": conditions,
        }

    def _get_node_roles(self, labels: dict[str, str]) -> list[str]:
        """获取 Node 角色"""
        roles = []
        if labels.get("node-role.kubernetes.io/master") or labels.get("node-role.kubernetes.io/control-plane"):
            roles.append("master")
        if labels.get("node-role.kubernetes.io/worker"):
            roles.append("worker")
        return roles or ["worker"]

    def _spark_app_to_dict(self, app: dict[str, Any]) -> dict[str, Any]:
        """转换 Spark Application 为字典"""
        metadata = app.get("metadata", {})
        status = app.get("status", {})
        spec = app.get("spec", {})

        return {
            "name": metadata.get("name"),
            "namespace": metadata.get("namespace"),
            "status": status.get("applicationState", {}).get("state", "UNKNOWN"),
            "driver_pod": status.get("driverInfo", {}).get("podName"),
            "executor_count": len(status.get("executorState", {})),
            "start_time": status.get("lastSubmissionAttemptTime"),
            "end_time": status.get("terminationTime"),
            "error_message": status.get("applicationState", {}).get("errorMessage"),
            "spark_version": spec.get("sparkVersion"),
            "mode": spec.get("mode"),
        }

    # ============ Mock 数据 ============

    def _mock_pods(self, namespace: str) -> list[dict[str, Any]]:
        """Mock Pod 列表"""
        return [
            {
                "name": "spark-etl-job-001-driver",
                "namespace": namespace,
                "status": "Succeeded",
                "pod_ip": "10.0.0.1",
                "node_name": "node-1",
                "labels": {"spark-role": "driver", "app": "spark-etl-job-001"},
                "containers": [{"name": "spark-kubernetes-driver", "image": "spark:3.5"}],
            },
            {
                "name": "spark-analytics-002-driver",
                "namespace": namespace,
                "status": "Running",
                "pod_ip": "10.0.0.2",
                "node_name": "node-2",
                "labels": {"spark-role": "driver", "app": "spark-analytics-002"},
                "containers": [{"name": "spark-kubernetes-driver", "image": "spark:3.5"}],
            },
        ]

    def _mock_pod(self, name: str, namespace: str) -> dict[str, Any]:
        """Mock Pod 详情"""
        return {
            "name": name,
            "namespace": namespace,
            "status": "Running",
            "pod_ip": "10.0.0.100",
            "node_name": "node-1",
            "labels": {},
            "containers": [],
        }

    def _mock_logs(self, name: str) -> str:
        """Mock 日志"""
        return f"""
INFO SparkContext: Running Spark version 3.5.0
INFO SparkContext: Submitted application: {name}
INFO Executor: Starting executor ID 0 on host node-1
INFO TaskSetManager: Starting task 0.0 in stage 0.0
INFO TaskSetManager: Finished task 0.0 in stage 0.0
INFO SparkContext: Spark application finished
"""

    def _mock_nodes(self) -> list[dict[str, Any]]:
        """Mock Node 列表"""
        return [
            {"name": "node-1", "status": "Ready", "roles": ["master"], "addresses": [{"type": "InternalIP", "address": "192.168.1.1"}]},
            {"name": "node-2", "status": "Ready", "roles": ["worker"], "addresses": [{"type": "InternalIP", "address": "192.168.1.2"}]},
            {"name": "node-3", "status": "Ready", "roles": ["worker"], "addresses": [{"type": "InternalIP", "address": "192.168.1.3"}]},
        ]

    def _mock_node(self, name: str) -> dict[str, Any]:
        """Mock Node 详情"""
        return {"name": name, "status": "Ready", "roles": ["worker"], "addresses": []}

    def _mock_spark_apps(self, namespace: str) -> list[dict[str, Any]]:
        """Mock Spark Application 列表"""
        return [
            {"name": "spark-etl-job-001", "namespace": namespace, "status": "COMPLETED", "driver_pod": "spark-etl-job-001-driver", "executor_count": 2},
            {"name": "spark-analytics-002", "namespace": namespace, "status": "RUNNING", "driver_pod": "spark-analytics-002-driver", "executor_count": 4},
            {"name": "spark-batch-load-003", "namespace": namespace, "status": "FAILED", "driver_pod": "spark-batch-load-003-driver", "executor_count": 2, "error_message": "OOM"},
        ]

    def _mock_spark_app(self, name: str, namespace: str) -> dict[str, Any]:
        """Mock Spark Application 详情"""
        return {"name": name, "namespace": namespace, "status": "RUNNING", "driver_pod": f"{name}-driver", "executor_count": 2}


# 全局实例
_k8s_client: Optional[K8sClient] = None


def get_k8s_client(namespace: str = "default") -> K8sClient:
    """获取全局 K8s 客户端"""
    global _k8s_client
    if _k8s_client is None:
        _k8s_client = K8sClient(namespace)
    return _k8s_client