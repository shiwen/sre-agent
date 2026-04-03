"""API 路由聚合"""

from fastapi import APIRouter

from app.api.v1 import chat, patrol, queue, spark

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(spark.router, prefix="/spark", tags=["spark"])
api_router.include_router(queue.router, prefix="/queues", tags=["queue"])
api_router.include_router(patrol.router, prefix="/patrol", tags=["patrol"])
