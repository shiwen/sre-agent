"""SRE Agent - FastAPI 应用入口"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理"""
    # 启动
    setup_logging()
    logger.info("sre_agent_starting", version=settings.APP_VERSION)

    # TODO: 初始化 LLM Registry
    # TODO: 初始化 K8s Client
    # TODO: 启动巡检调度器

    yield

    # 关闭
    logger.info("sre_agent_shutdown")


app = FastAPI(
    title="SRE Agent",
    description="SRE Agent for Spark on K8s Operations",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """健康检查端点"""
    return {"status": "healthy", "version": settings.APP_VERSION}
