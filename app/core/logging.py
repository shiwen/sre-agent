"""结构化日志配置"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.typing import Processor


def setup_logging() -> None:
    """配置结构化日志"""

    # 共享处理器
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # 根据环境选择渲染器
    if sys.stdout.isatty():
        # 开发环境：彩色输出
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 生产环境：JSON 输出
        renderer = structlog.processors.JSONRenderer()

    # 配置 structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.ExceptionRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            min_level="INFO" if not True else "DEBUG"  # TODO: 使用 settings.DEBUG
        ),
        cache_logger_on_first_use=True,
    )
