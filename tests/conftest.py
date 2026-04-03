"""Pytest 配置"""

from typing import Any

import pytest


@pytest.fixture
def mock_settings() -> Any:
    """Mock 配置"""
    from app.core.config import Settings

    return Settings(
        ENV="test",
        DEBUG=True,
        K8S_NAMESPACE="test-ns",
    )


@pytest.fixture
def mock_k8s_client() -> Any:
    """Mock K8s 客户端"""
    # TODO: 实现完整的 Mock K8s Client
    return None
