from typing import Type, Dict, Any
from threading import Lock
from collections import defaultdict
from logging import getLogger

from .config import RuntimeConfig
from ..base_cls import BaseApiT

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
        self._instances: Dict[Type, Dict[str, Any]] = defaultdict(dict)
        # Type[BaseApiT] - {config_key - BaseApiT}

    def get_api(
        self,
        cls: Type[BaseApiT],
        config_key: str,
    ) -> BaseApiT:
        """
        获取API实例

        Args:
            cls: API类
            config_key: 配置键
        """
        _log.debug(f"读取 {config_key} 的 {cls.__name__} 实例")
        with self._lock:
            if config_key not in self._instances[cls]:
                self._instances[cls][config_key] = cls.create(
                    self,
                    config_key = config_key
                )

        return self._instances[cls][config_key]

    get = get_api
