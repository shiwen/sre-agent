"""会话管理单元测试"""


from langchain_core.messages import AIMessage, HumanMessage
import pytest

from app.agent.memory.session import Session, SessionManager


@pytest.mark.unit
def test_session_create():
    """测试会话创建"""
    session = Session(user_id="test_user")

    assert session.id
    assert session.user_id == "test_user"
    assert session.status == "active"
    assert len(session.messages) == 0


@pytest.mark.unit
def test_session_add_message():
    """测试添加消息"""
    session = Session()

    session.add_message(HumanMessage(content="你好"))
    session.add_message(AIMessage(content="你好！有什么可以帮助你的？"))

    assert len(session.messages) == 2
    assert isinstance(session.messages[0], HumanMessage)
    assert isinstance(session.messages[1], AIMessage)


@pytest.mark.unit
def test_session_context_string():
    """测试上下文字符串"""
    session = Session()

    session.add_message(HumanMessage(content="查询 Spark 任务"))
    session.add_message(AIMessage(content="找到 3 个任务"))

    context = session.get_context_string()

    assert "用户: 查询 Spark 任务" in context
    assert "助手: 找到 3 个任务" in context


@pytest.mark.unit
def test_session_summary():
    """测试会话摘要"""
    session = Session(summary="之前讨论了 Spark 任务失败的问题")

    context = session.get_context_string()

    assert "历史摘要" in context
    assert "Spark 任务失败" in context


@pytest.mark.unit
def test_session_serialize():
    """测试会话序列化"""
    session = Session(user_id="test_user")
    session.add_message(HumanMessage(content="测试消息"))

    data = session.to_dict()

    assert data["id"] == session.id
    assert data["user_id"] == "test_user"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["type"] == "human"


@pytest.mark.unit
def test_session_deserialize():
    """测试会话反序列化"""
    data = {
        "id": "test-session-id",
        "user_id": "test_user",
        "created_at": "2026-04-03T10:00:00",
        "updated_at": "2026-04-03T10:30:00",
        "messages": [
            {"type": "human", "content": "测试"},
            {"type": "ai", "content": "回复"},
        ],
        "summary": None,
        "metadata": {},
        "status": "active",
    }

    session = Session.from_dict(data)

    assert session.id == "test-session-id"
    assert session.user_id == "test_user"
    assert len(session.messages) == 2
    assert isinstance(session.messages[0], HumanMessage)


@pytest.mark.unit
def test_session_manager_create():
    """测试 Session Manager 创建会话"""
    manager = SessionManager()

    session = manager.create(user_id="test_user")

    assert session.id
    assert session.user_id == "test_user"

    # 会话应该被保存
    assert manager.get(session.id) == session


@pytest.mark.unit
def test_session_manager_get_or_create():
    """测试获取或创建会话"""
    manager = SessionManager()

    # 创建新会话
    session1 = manager.get_or_create(user_id="test_user")
    assert session1.id

    # 获取已存在的会话
    session2 = manager.get_or_create(session_id=session1.id)
    assert session2.id == session1.id


@pytest.mark.unit
def test_session_manager_delete():
    """测试删除会话"""
    manager = SessionManager()

    session = manager.create()
    session_id = session.id

    # 删除会话
    result = manager.delete(session_id)
    assert result is True

    # 会话应该不存在
    assert manager.get(session_id) is None


@pytest.mark.unit
def test_session_manager_list():
    """测试列出会话"""
    manager = SessionManager()

    # 创建多个会话
    manager.create(user_id="user1")
    manager.create(user_id="user1")
    manager.create(user_id="user2")

    # 按用户筛选
    sessions = manager.list_sessions(user_id="user1")
    assert len(sessions) == 2

    # 所有会话
    all_sessions = manager.list_sessions()
    assert len(all_sessions) >= 3
