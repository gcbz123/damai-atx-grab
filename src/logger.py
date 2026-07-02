"""日志模块 - 基于 loguru 的结构化日志记录"""

import sys
from pathlib import Path
from loguru import logger


class LoggerManager:
    """日志管理器，统一日志输出格式与销毁"""

    _initialized = False

    @classmethod
    def init(cls, log_dir: str = "logs", level: str = "DEBUG"):
        """初始化日志配置

        Args:
            log_dir: 日志目录路径
            level: 日志级别 DEBUG/INFO/WARNING/ERROR
        """
        if cls._initialized:
            return

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 移除默认 handler
        logger.remove()

        # 控制台输出（彩色）
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <7}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=level,
            colorize=True,
        )

        # 文件输出（完整信息）
        logger.add(
            log_path / "run_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {name}:{function}:{line} | {message}",
            level=level,
            rotation="100 MB",
            retention="30 days",
            compression="zip",
        )

        # 错误日志单独文件
        logger.add(
            log_path / "error_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation="50 MB",
            retention="30 days",
        )

        cls._initialized = True
        logger.debug("日志模块初始化完成")

    @classmethod
    def reset(cls):
        """重置日志配置（用于测试）"""
        logger.remove()
        cls._initialized = False
