"""SRE Agent 配置管理"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SettingsConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 基础配置
    APP_NAME: str = "SRE Agent"
    APP_VERSION: str = "0.1.0"
    ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = True

    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"])

    # LLM 配置
    LLM_PRIMARY_ENDPOINT: str | None = None
    LLM_PRIMARY_API_KEY: str | None = None
    LLM_PRIMARY_MODEL: str = "gpt-4"
    LLM_FALLBACK_ENDPOINT: str | None = None
    LLM_FALLBACK_API_KEY: str | None = None
    LLM_FALLBACK_MODEL: str = "gpt-3.5-turbo"

    # K8s 配置
    K8S_NAMESPACE: str = "sre-agent-dev"
    K8S_API_TIMEOUT: int = 30

    # Spark 配置
    SPARK_OPERATOR_NAMESPACE: str = "spark-operator"

    # YuniKorn 配置
    YUNIKORN_API_URL: str = "http://yunikorn-scheduler:9080"

    # History Server
    SPARK_HISTORY_SERVER_URL: str | None = None

    # 巡检配置
    PATROL_INTERVAL_MINUTES: int = 60
    PATROL_ENABLED: bool = True

    # 会话配置
    SESSION_MAX_MESSAGES: int = 50
    SESSION_SUMMARY_THRESHOLD: int = 10

    # 推送配置
    FEISHU_BOT_TOKEN: str | None = None


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


# 全局配置实例
settings = get_settings()