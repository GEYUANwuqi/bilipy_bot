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
import re
import sys
import warnings
from dataclasses import dataclass, field
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from threading import RLock
from types import TracebackType
from typing import Any, Self

from ._ansi import Ansi as Color
from ._ansi import enable_ansi, is_ansi_supported

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

_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


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
        self.fmt_dict = {
            level_name: (
                format_string
                if use_color
                else _ANSI_ESCAPE_PATTERN.sub("", format_string)
            )
            for level_name, format_string in fmt_dict.items()
        }
        self.use_color = use_color

        # 为每个级别预创建Formatter实例，提高性能
        self._formatters = {}
        for level_name, fmt in self.fmt_dict.items():
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


@dataclass(frozen=True, slots=True)
class _LoggingConfig:
    console_level: int
    file_level: int
    root_file_path: Path
    redirect_paths: tuple[tuple[str, Path], ...]
    backup_count: int
    use_color: bool
    stream_id: int
    stream: Any = field(compare=False, hash=False, repr=False)


@dataclass(frozen=True, slots=True)
class _LoggerSnapshot:
    handlers: tuple[logging.Handler, ...]
    level: int
    propagate: bool


@dataclass(slots=True)
class _ActiveLogging:
    config: _LoggingConfig
    generation: int
    root_snapshot: _LoggerSnapshot
    redirect_snapshots: dict[logging.Logger, _LoggerSnapshot]
    managed_handlers: tuple[logging.Handler, ...]
    leases: int = 1


_logging_lock = RLock()
_active_logging: _ActiveLogging | None = None
_logging_generation = 0


class LoggingLease:
    """一次进程级日志配置所有权.

    相同配置可以由多个应用共享. 最后一份 lease 关闭时,
    ButterBot 关闭自己创建的 handler, 并恢复原有 logger 状态.
    """

    __slots__ = ("_generation", "_released")

    def __init__(self, generation: int) -> None:
        self._generation = generation
        self._released = False

    @property
    def released(self) -> bool:
        """返回当前 lease 是否已经释放."""
        return self._released

    def close(self) -> None:
        """释放当前所有权, 重复调用无操作."""
        if self._released:
            return
        with _logging_lock:
            if self._released:
                return
            _release_logging(self._generation)
            self._released = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _stream_supports_color(stream: Any) -> bool:
    try:
        return bool(stream.isatty()) and is_ansi_supported()
    except (AttributeError, OSError):
        return False


def _load_logging_config(console_level: str | None) -> _LoggingConfig:
    resolved_console_level = console_level or os.getenv("LOG_LEVEL", "INFO").upper()
    file_level = os.getenv("FILE_LOG_LEVEL", "DEBUG").upper()
    console_log_level = _get_valid_log_level(resolved_console_level, "INFO")
    file_log_level = _get_valid_log_level(file_level, "DEBUG")

    try:
        backup_count = int(os.getenv("BACKUP_COUNT", "7"))
        if backup_count < 0:
            raise ValueError
    except ValueError:
        backup_count = 7
        warnings.warn("BACKUP_COUNT 必须是非负整数, 将使用默认值 7")

    log_dir = Path(os.getenv("LOG_FILE_PATH", "./logs"))
    root_file_path = _resolve_log_file(
        log_dir,
        os.getenv("LOG_FILE_NAME", "bot.log"),
    )
    redirect_paths = tuple(
        sorted(
            (
                logger_name,
                _resolve_log_file(log_dir, redirect_file_name),
            )
            for logger_name, redirect_file_name in _load_redirect_rules().items()
        )
    )
    stream = sys.stderr
    return _LoggingConfig(
        console_level=console_log_level,
        file_level=file_log_level,
        root_file_path=root_file_path,
        redirect_paths=redirect_paths,
        backup_count=backup_count,
        use_color=_stream_supports_color(stream),
        stream_id=id(stream),
        stream=stream,
    )


def _snapshot_logger(logger: logging.Logger) -> _LoggerSnapshot:
    return _LoggerSnapshot(
        handlers=tuple(logger.handlers),
        level=logger.level,
        propagate=logger.propagate,
    )


def _restore_logger(logger: logging.Logger, snapshot: _LoggerSnapshot) -> None:
    logger.handlers = list(snapshot.handlers)
    logger.setLevel(snapshot.level)
    logger.propagate = snapshot.propagate


def _install_logging(config: _LoggingConfig, generation: int) -> _ActiveLogging:
    root_logger = logging.getLogger()
    root_snapshot = _snapshot_logger(root_logger)
    redirect_snapshots = {
        logging.getLogger(logger_name): _snapshot_logger(logging.getLogger(logger_name))
        for logger_name, _ in config.redirect_paths
    }
    file_formatter = DynamicFormatter(
        fmt_dict=LOG_MESSAGE_FORMATS["file"],
        datefmt="%Y-%m-%d %H:%M:%S",
        use_color=False,
    )
    managed_handlers: list[logging.Handler] = []
    redirect_handlers: dict[logging.Logger, TimedRotatingFileHandler] = {}
    try:
        for path in {
            config.root_file_path,
            *(path for _, path in config.redirect_paths),
        }:
            path.parent.mkdir(parents=True, exist_ok=True)

        enable_ansi()
        console_handler = logging.StreamHandler(config.stream)
        console_handler.setLevel(config.console_level)
        console_handler.setFormatter(
            DynamicFormatter(
                fmt_dict=LOG_MESSAGE_FORMATS["console"],
                datefmt="%H:%M:%S",
                use_color=config.use_color,
            )
        )
        managed_handlers.append(console_handler)

        root_file_handler = TimedRotatingFileHandler(
            filename=config.root_file_path,
            when="midnight",
            interval=1,
            backupCount=config.backup_count,
            encoding="utf-8",
            utc=True,
        )
        root_file_handler.setLevel(config.file_level)
        root_file_handler.setFormatter(file_formatter)
        managed_handlers.append(root_file_handler)

        for logger_name, redirect_file_path in config.redirect_paths:
            file_handler = TimedRotatingFileHandler(
                filename=redirect_file_path,
                when="midnight",
                interval=1,
                backupCount=config.backup_count,
                encoding="utf-8",
                utc=True,
            )
            file_handler.setLevel(config.file_level)
            file_handler.setFormatter(file_formatter)
            redirect_handlers[logging.getLogger(logger_name)] = file_handler
            managed_handlers.append(file_handler)
    except Exception:
        for handler in managed_handlers:
            handler.close()
        raise

    try:
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers = managed_handlers[:2]
        for logger, handler in redirect_handlers.items():
            logger.setLevel(config.file_level)
            logger.handlers = [handler]
            logger.propagate = False
    except BaseException:
        _restore_logger(root_logger, root_snapshot)
        for logger, snapshot in redirect_snapshots.items():
            _restore_logger(logger, snapshot)
        for handler in managed_handlers:
            handler.close()
        raise

    return _ActiveLogging(
        config=config,
        generation=generation,
        root_snapshot=root_snapshot,
        redirect_snapshots=redirect_snapshots,
        managed_handlers=tuple(managed_handlers),
    )


def _release_logging(generation: int) -> None:
    global _active_logging

    active = _active_logging
    if active is None or active.generation != generation:
        return
    active.leases -= 1
    if active.leases > 0:
        return

    _restore_logger(logging.getLogger(), active.root_snapshot)
    for logger, snapshot in active.redirect_snapshots.items():
        _restore_logger(logger, snapshot)
    for handler in active.managed_handlers:
        handler.close()
    _active_logging = None


def setup_logging(console_level: str | None = None) -> LoggingLease:
    """取得进程级日志配置的一份共享 lease.

    活跃 lease 期间, root logger 由 ButterBot 管理, 因此任意保持
    ``propagate=True`` 的命名 logger 都使用同一格式. 同配置调用共享
    handler; 并存的不同配置会被拒绝.
    """
    global _active_logging, _logging_generation

    config = _load_logging_config(console_level)
    with _logging_lock:
        if _active_logging is not None:
            if _active_logging.config != config:
                raise RuntimeError("已有 BotApp 使用不同的进程级日志配置")
            _active_logging.leases += 1
            return LoggingLease(_active_logging.generation)

        _logging_generation += 1
        _active_logging = _install_logging(config, _logging_generation)
        return LoggingLease(_logging_generation)
