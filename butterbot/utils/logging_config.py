# -------------------------
# @Author       : Fish-LP fish.zh@outlook.com
# @Date         : 2025-02-12 13:41:02
# @LastEditors  : Fish-LP fish.zh@outlook.com
# @LastEditTime : 2025-06-22 21:51:42
# @Description  : 日志格式化
# @Copyright (c) 2025 by Fish-LP, MIT 使用许可协议
# -------------------------
import json
import logging
import os
import warnings
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .terminal import Color, set_console_mode

__author__ = "Fish-LP <Fish.zh@outlook.com>"
__status__ = "dev"
__version__ = "2.1.1-dev"

# NOTE: 这里保存的是针对不同目标（console/file）和不同日志级别的消息格式模板
LOG_MESSAGE_FORMATS = {
    "console": {
        "DEBUG": (
            Color.CYAN
            + "[%(asctime)s.%(msecs)s]"
            + Color.RESET
            + " "
            + Color.BLUE
            + "%(colored_levelname)-8s"
            + Color.RESET
            + " "
            + Color.GRAY
            + "[%(threadName)s|%(processName)s]"
            + Color.RESET
            + " "
            + Color.MAGENTA
            + "%(name)s"
            + Color.RESET
            + " "
            + Color.YELLOW
            + "%(filename)s:%(lineno)d %(funcName)s"
            + Color.RESET
            + " "
            + Color.RESET
            + "| %(message)s"
            + Color.RESET
        ),
        "INFO": (
            Color.CYAN
            + "[%(asctime)s]"
            + Color.RESET
            + " "
            + Color.GREEN
            + "%(colored_levelname)-8s"
            + Color.RESET
            + " "
            + Color.MAGENTA
            + "%(name)s"
            + Color.RESET
            + " ➜ "
            + Color.RESET
            + "%(message)s"
            + Color.RESET
        ),
        "WARNING": (
            Color.CYAN
            + "[%(asctime)s]"
            + Color.RESET
            + " "
            + Color.YELLOW
            + "%(colored_levelname)-8s"
            + Color.RESET
            + " "
            + Color.MAGENTA
            + "%(name)s"
            + Color.RESET
            + " "
            + Color.YELLOW
            + "➜"
            + Color.RESET
            + " "
            + Color.RESET
            + "%(message)s"
            + Color.RESET
        ),
        "ERROR": (
            Color.CYAN
            + "[%(asctime)s]"
            + Color.RESET
            + " "
            + Color.RED
            + "%(colored_levelname)-8s"
            + Color.RESET
            + " "
            + Color.GRAY
            + "[%(filename)s]"
            + Color.RESET
            + Color.MAGENTA
            + "%(name)s:%(lineno)d"
            + Color.RESET
            + " "
            + Color.RED
            + "➜"
            + Color.RESET
            + " "
            + Color.RESET
            + "%(message)s"
            + Color.RESET
        ),
        "CRITICAL": (
            Color.CYAN
            + "[%(asctime)s]"
            + Color.RESET
            + " "
            + Color.RED
            + Color.BOLD
            + "%(colored_levelname)-8s"
            + Color.RESET
            + " "
            + Color.GRAY
            + "{%(module)s}"
            + Color.RESET
            + Color.MAGENTA
            + "[%(filename)s]"
            + Color.RESET
            + Color.MAGENTA
            + "%(name)s:%(lineno)d"
            + Color.RESET
            + " "
            + Color.RED
            + "➜"
            + Color.RESET
            + " "
            + Color.RESET
            + "%(message)s"
            + Color.RESET
        ),
    },
    "file": {
        "DEBUG": "[%(asctime)s] %(levelname)-8s [%(threadName)s|%(processName)s] %(name)s (%(filename)s:%(funcName)s:%(lineno)d) | %(message)s",
        "INFO": "[%(asctime)s] %(levelname)-8s %(name)s ➜ %(message)s",
        "WARNING": "[%(asctime)s] %(levelname)-8s %(name)s ➜ %(message)s",
        "ERROR": "[%(asctime)s] %(levelname)-8s [%(filename)s]%(name)s:%(lineno)d ➜ %(message)s",
        "CRITICAL": "[%(asctime)s] %(levelname)-8s {%(module)s}[%(filename)s]%(name)s:%(lineno)d ➜ %(message)s",
    },
}

# 日志级别颜色映射
LOG_LEVEL_TO_COLOR = {
    "DEBUG": Color.CYAN,
    "INFO": Color.GREEN,
    "WARNING": Color.YELLOW,
    "ERROR": Color.RED,
    "CRITICAL": Color.MAGENTA,
}

_managed_handlers: list[tuple[logging.Logger, logging.Handler]] = []
_redirect_logger_state: dict[logging.Logger, tuple[int, bool]] = {}


# 定义动态格式化器，根据日志级别选择不同的格式
class DynamicFormatter(logging.Formatter):
    """根据日志记录级别动态选择格式的格式化器"""

    def __init__(
        self, fmt_dict: dict, datefmt: str | None = None, use_color: bool = True
    ):
        """
        初始化动态格式化器

        Args:
            fmt_dict: 包含不同日志级别格式字符串的字典，键为级别名称（如"DEBUG"）
            datefmt: 日期时间格式字符串
            use_color: 是否使用颜色
        """
        super().__init__(datefmt=datefmt)
        self.fmt_dict = fmt_dict
        self.use_color = use_color

        # 为每个级别预创建Formatter实例，提高性能
        self._formatters = {}
        for level_name, fmt in fmt_dict.items():
            self._formatters[level_name] = logging.Formatter(fmt, datefmt=datefmt)

        # 默认格式（使用第一个可用的格式）
        self._default_formatter = list(self._formatters.values())[0]

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，根据记录级别选择对应的格式"""
        # 动态颜色处理
        if self.use_color:
            record.colored_levelname = "%s%8s%s" % (
                LOG_LEVEL_TO_COLOR.get(record.levelname, Color.RESET),
                record.levelname,
                Color.RESET,
            )
            # 添加统一颜色字段
            record.colored_name = "%s%s%s" % (Color.MAGENTA, record.name, Color.RESET)
            # 添加毫秒信息用于ERROR级别格式
        else:
            record.colored_levelname = record.levelname
            record.colored_name = record.name

        # 根据记录级别选择格式
        level_name = record.levelname
        formatter = self._formatters.get(level_name, self._default_formatter)

        try:
            return formatter.format(record)
        except Exception as e:
            warnings.warn("日志格式化错误: %s" % e)
            # 使用默认格式作为备选
            return self._default_formatter.format(record)


def _get_valid_log_level(level_name: str, default: str) -> int:
    """验证并获取有效的日志级别"""
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        warnings.warn(
            "Invalid log level: %s, using %s instead." % (level_name, default)
        )
        return getattr(logging, default)
    return level


def _resolve_log_file(log_dir: Path, file_name: str) -> Path:
    """解析日志文件路径，并阻止文件逃逸出配置目录."""
    if not file_name or Path(file_name).is_absolute():
        raise ValueError("日志文件名必须是 LOG_FILE_PATH 下的非空相对路径")

    resolved_dir = log_dir.resolve()
    resolved_file = (resolved_dir / file_name).resolve()
    try:
        resolved_file.relative_to(resolved_dir)
    except ValueError as exc:
        raise ValueError("日志文件必须位于 LOG_FILE_PATH 配置目录内") from exc
    if resolved_file == resolved_dir:
        raise ValueError("日志文件名不能指向 LOG_FILE_PATH 目录本身")
    return resolved_file


def _load_redirect_rules() -> dict[str, str]:
    """读取并校验日志重定向规则."""
    redirect_rules_json = os.getenv("LOG_REDIRECT_RULES", "{}")
    try:
        raw_rules = json.loads(redirect_rules_json)
    except json.JSONDecodeError:
        warnings.warn("LOG_REDIRECT_RULES 不是有效的 JSON，将忽略重定向规则")
        return {}

    if not isinstance(raw_rules, dict):
        warnings.warn("LOG_REDIRECT_RULES 必须是记录器名称到文件名的对象")
        return {}

    redirect_rules: dict[str, str] = {}
    for logger_name, file_name in raw_rules.items():
        if not isinstance(logger_name, str) or not logger_name:
            raise ValueError("日志重定向规则中的记录器名称必须是非空字符串")
        if not isinstance(file_name, str):
            raise ValueError("日志重定向规则中的日志文件名必须是字符串")
        redirect_rules[logger_name] = file_name
    return redirect_rules


def _clear_managed_handlers() -> None:
    """移除并关闭上一次初始化创建的 handler."""
    for logger, handler in _managed_handlers:
        logger.removeHandler(handler)
        handler.close()
    _managed_handlers.clear()

    for logger, (level, propagate) in _redirect_logger_state.items():
        logger.setLevel(level)
        logger.propagate = propagate
    _redirect_logger_state.clear()


def setup_logging(console_level: str | None = None) -> None:
    """显式设置日志系统，支持根据记录器名称重定向到不同文件."""
    # 环境变量读取
    console_level = console_level or os.getenv("LOG_LEVEL", "INFO").upper()
    file_level = os.getenv("FILE_LOG_LEVEL", "DEBUG").upper()

    # 验证并转换日志级别
    console_log_level = _get_valid_log_level(console_level, "INFO")
    file_log_level = _get_valid_log_level(file_level, "DEBUG")

    # 文件路径配置 - 使用固定名称，不使用日期
    log_dir = os.getenv("LOG_FILE_PATH", "./logs")
    file_name = os.getenv("LOG_FILE_NAME", "bot.log")  # 改为固定名称

    # 备份数量验证
    try:
        backup_count = int(os.getenv("BACKUP_COUNT", "7"))
        if backup_count < 0:
            raise ValueError
    except ValueError:
        backup_count = 7
        warnings.warn("BACKUP_COUNT 必须是非负整数，将使用默认值 7")

    # 在修改现有日志配置前完成全部路径校验。
    log_dir_path = Path(log_dir)
    root_file_path = _resolve_log_file(log_dir_path, file_name)
    redirect_rules = _load_redirect_rules()
    redirect_paths = {
        logger_name: _resolve_log_file(log_dir_path, redirect_file_name)
        for logger_name, redirect_file_name in redirect_rules.items()
    }

    # ===== 1. 配置根记录器 =====
    root_logger = logging.getLogger()

    # 先创建完整的新 handler 集合；失败时保留当前日志配置。
    file_formatter = DynamicFormatter(
        fmt_dict=LOG_MESSAGE_FORMATS["file"],
        datefmt="%Y-%m-%d %H:%M:%S",
        use_color=False,
    )
    console_handler: logging.StreamHandler | None = None
    root_file_handler: TimedRotatingFileHandler | None = None
    redirect_handlers: dict[str, TimedRotatingFileHandler] = {}
    try:
        for path in {root_file_path, *redirect_paths.values()}:
            path.parent.mkdir(parents=True, exist_ok=True)

        set_console_mode()
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_log_level)
        console_handler.setFormatter(
            DynamicFormatter(
                fmt_dict=LOG_MESSAGE_FORMATS["console"],
                datefmt="%H:%M:%S",
                use_color=True,
            )
        )

        root_file_handler = TimedRotatingFileHandler(
            filename=root_file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            utc=True,
        )
        root_file_handler.setLevel(file_log_level)
        root_file_handler.setFormatter(file_formatter)

        for logger_name, redirect_file_path in redirect_paths.items():
            file_handler = TimedRotatingFileHandler(
                filename=redirect_file_path,
                when="midnight",
                interval=1,
                backupCount=backup_count,
                encoding="utf-8",
                utc=True,
            )
            file_handler.setLevel(file_log_level)
            file_handler.setFormatter(file_formatter)
            redirect_handlers[logger_name] = file_handler
    except Exception:
        if console_handler is not None:
            console_handler.close()
        if root_file_handler is not None:
            root_file_handler.close()
        for file_handler in redirect_handlers.values():
            file_handler.close()
        raise

    assert console_handler is not None
    assert root_file_handler is not None

    # 所有新 handler 创建成功后再替换上一次由本模块管理的配置。
    _clear_managed_handlers()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = [console_handler, root_file_handler]
    _managed_handlers.extend(
        [(root_logger, console_handler), (root_logger, root_file_handler)]
    )

    for logger_name, file_handler in redirect_handlers.items():
        logger = logging.getLogger(logger_name)
        _redirect_logger_state[logger] = (logger.level, logger.propagate)
        logger.setLevel(file_log_level)
        logger.addHandler(file_handler)
        logger.propagate = False
        _managed_handlers.append((logger, file_handler))
