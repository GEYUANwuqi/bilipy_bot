from collections import defaultdict
from logging import getLogger
from threading import Lock
from typing import Any

from bilipy_bot.app.config import RuntimeConfig
from bilipy_bot.core.api import BaseApiT

_log = getLogger("APIContext")


class APIContext:
    """API上下文管理，负责管理 API 单例和配置."""

    def __init__(self, config: RuntimeConfig):
        """初始化 APIContext 实例.
        Args:
            config (RuntimeConfig): 运行时API配置实例
        """
        self.config = config
        self._lock = Lock()
        self._instances: dict[type, dict[str, Any]] = defaultdict(dict)
        # Type[BaseApiT] - {config_key - BaseApiT}

    def get_api(
        self,
        cls: type[BaseApiT],
        config_key: str,
    ) -> BaseApiT:
        """
        获取API实例

        Args:
            cls: API类
            config_key: 配置键
        """
        _log.debug("读取 %s 的 %s 实例", config_key, cls.__name__)
        with self._lock:
            if config_key not in self._instances[cls]:
                self._instances[cls][config_key] = cls.create(
                    self, config_key=config_key
                )

        return self._instances[cls][config_key]

    def clear(self) -> None:
        """清空所有缓存的 API 单例实例，主要用于测试隔离."""
        with self._lock:
            self._instances.clear()

    get = get_api
