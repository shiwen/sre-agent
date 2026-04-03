"""SRE Agent 主入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app
from structlog import get_logger

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = get_logger()

# Prometheus 指标
REQUEST_COUNT = Counter(
    "sre_agent_requests_total",
    "Total requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "sre_agent_request_latency_seconds",
    "Request latency",
    ["method", "endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    setup_logging()
    logger.info("sre_agent_starting", version="0.1.0", env=settings.ENV)

    yield

    # 关闭
    logger.info("sre_agent_stopping")


app = FastAPI(
    title="SRE Agent",
    description="SRE Agent for Spark on Kubernetes operations",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(v1_router, prefix="/api")


# 健康检查
@app.get("/health")
async def health_check() -> dict:
    """健康检查端点"""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root() -> dict:
    """根端点"""
    return {
        "name": "SRE Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Prometheus 指标端点
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
