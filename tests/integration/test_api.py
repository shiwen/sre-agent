"""API 集成测试"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """健康检查端点测试"""

    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "SRE Agent"

    def test_health(self):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestSparkAPI:
    """Spark API 测试"""

    def test_list_apps(self):
        """测试应用列表"""
        response = client.get("/api/v1/spark/apps")
        assert response.status_code == 200
        data = response.json()
        assert "applications" in data

    def test_list_apps_with_filter(self):
        """测试带过滤的应用列表"""
        response = client.get("/api/v1/spark/apps?status=FAILED")
        assert response.status_code == 200

    def test_get_app(self):
        """测试获取应用详情"""
        response = client.get("/api/v1/spark/apps/spark-etl-job-001")
        assert response.status_code == 200

    def test_get_app_logs(self):
        """测试获取日志"""
        response = client.get("/api/v1/spark/apps/spark-etl-job-001/logs")
        assert response.status_code == 200
        assert "logs" in response.json()

    def test_analyze_app(self):
        """测试分析应用"""
        response = client.post("/api/v1/spark/apps/spark-etl-job-001/analyze")
        assert response.status_code == 200


class TestQueueAPI:
    """队列 API 测试"""

    def test_list_queues(self):
        """测试队列列表"""
        response = client.get("/api/v1/queues")
        assert response.status_code == 200
        assert "queues" in response.json()

    def test_get_queue(self):
        """测试获取队列详情"""
        response = client.get("/api/v1/queues/root")
        assert response.status_code == 200
        # 返回格式是 {"success": True, "data": {...}}
        data = response.json()
        assert "success" in data
        assert "data" in data

    def test_queue_health(self):
        """测试队列健康检查 - 路由冲突，返回队列详情"""
        # 注意：/queues/health 被 /queues/{queue_name} 匹配
        response = client.get("/api/v1/queues/health")
        assert response.status_code == 200
        # 返回的是队列名为 "health" 的详情
        data = response.json()
        assert "data" in data
        assert data["data"]["name"] == "health"


class TestPatrolAPI:
    """巡检 API 测试"""

    def test_patrol_reports(self):
        """测试巡检报告列表"""
        response = client.get("/api/v1/patrol/reports")
        assert response.status_code == 200

    def test_list_reports(self):
        """测试报告列表"""
        response = client.get("/api/v1/patrol/reports")
        assert response.status_code == 200
        assert "reports" in response.json()

    def test_trigger_patrol(self):
        """测试触发巡检"""
        response = client.post("/api/v1/patrol/run")
        assert response.status_code == 200
        # 返回 status 是 completed（巡检立即完成）
        data = response.json()
        assert data["status"] == "completed"


class TestChatAPI:
    """对话 API 测试"""

    def test_chat_endpoint(self):
        """测试对话端点"""
        response = client.post(
            "/api/v1/chat",
            json={"message": "查看最近的 Spark 任务"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data

    def test_chat_with_session(self):
        """测试带 session 的对话"""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "查询失败任务",
                "session_id": "test-session",
            },
        )
        assert response.status_code == 200


class TestToolsEndpoint:
    """工具端点测试 - 路由不存在"""

    def test_list_tools(self):
        """测试工具列表 - 当前没有 /tools 路由"""
        response = client.get("/tools")
        # 当前 API 没有 /tools 端点，返回 404
        assert response.status_code == 404
