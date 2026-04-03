"""巡检调度器"""

from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from structlog import get_logger

from app.patrol.engine import PatrolReport, get_patrol_engine

logger = get_logger()


class PatrolScheduler:
    """巡检调度器"""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._job_id = "patrol_job"
        self._running = False
        self._notification_callback: Callable | None = None

    def set_notification_callback(self, callback: Callable) -> None:
        """设置通知回调函数"""
        self._notification_callback = callback

    def start(
        self,
        interval_minutes: int = 30,
        notification_callback: Callable | None = None,
    ) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("scheduler_already_running")
            return

        if notification_callback:
            self._notification_callback = notification_callback

        # 添加定时任务
        self._scheduler.add_job(
            self._run_patrol,
            IntervalTrigger(minutes=interval_minutes),
            id=self._job_id,
            name="Scheduled Patrol",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True

        logger.info(
            "scheduler_started",
            interval_minutes=interval_minutes,
            next_run=self._scheduler.get_job(self._job_id).next_run_time,
        )

    def start_with_cron(self, cron_expression: str) -> None:
        """使用 cron 表达式启动调度器"""
        if self._running:
            logger.warning("scheduler_already_running")
            return

        # 解析 cron 表达式
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        self._scheduler.add_job(
            self._run_patrol,
            CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            ),
            id=self._job_id,
            name="Scheduled Patrol",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True

        logger.info(
            "scheduler_started_cron",
            cron_expression=cron_expression,
        )

    def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return

        self._scheduler.shutdown(wait=False)
        self._running = False

        logger.info("scheduler_stopped")

    async def _run_patrol(self) -> PatrolReport:
        """执行巡检"""
        logger.info("scheduled_patrol_started")

        try:
            engine = get_patrol_engine()
            report = await engine.run_patrol()

            # 发送通知
            if self._notification_callback:
                try:
                    await self._notification_callback(report)
                except Exception as e:
                    logger.error("notification_failed", error=str(e))

            return report

        except Exception as e:
            logger.error("scheduled_patrol_failed", error=str(e))
            raise

    def get_status(self) -> dict:
        """获取调度状态"""
        if not self._running:
            return {
                "running": False,
                "next_run": None,
            }

        job = self._scheduler.get_job(self._job_id)
        return {
            "running": True,
            "next_run": job.next_run_time.isoformat() if job else None,
        }


# 全局实例
_patrol_scheduler: PatrolScheduler | None = None


def get_patrol_scheduler() -> PatrolScheduler:
    """获取全局巡检调度器"""
    global _patrol_scheduler
    if _patrol_scheduler is None:
        _patrol_scheduler = PatrolScheduler()
    return _patrol_scheduler
