"""API v1 路由聚合"""

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.patrol import router as patrol_router
from app.api.v1.queue import router as queue_router
from app.api.v1.spark import router as spark_router

router = APIRouter(prefix="/v1")

router.include_router(chat_router)
router.include_router(spark_router)
router.include_router(queue_router)
router.include_router(patrol_router)
router.include_router(metrics_router)
