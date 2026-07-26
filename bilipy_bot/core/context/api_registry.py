from __future__ import annotations

from collections import defaultdict
from logging import getLogger
from threading import RLock
from typing import TYPE_CHECKING, Any

from bilipy_bot.core.api import BaseApi, BaseApiT
from bilipy_bot.core.exceptions import ConfigError

if TYPE_CHECKING:
    from bilipy_bot.app.config import RuntimeConfig

_log = getLogger(__name__)


class ApiRegistry:
    """API 注册器，负责管理 API 单例和配置."""

    def __init__(self, config: "RuntimeConfig"):
        """初始化 ApiRegistry 实例.
        Args:
            config (RuntimeConfig): 运行时 API 配置实例
        """
        self.config = config
        # 用可重入锁：API 的 create() 是同步方法，允许在内部再取用别的 API
        # （create → get_api → 同一把锁），非重入锁会在这条路径上自死锁。
        self._lock = RLock()
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

    def require_config(self, config_key: str) -> Any:
        """读取必需的配置项，缺失时抛出明确错误.

        供 API 的 :meth:`BaseApi.create` 使用。直接用
        ``ctx.config.get_config(key)`` 时缺失的键会静默返回 ``None``，
        错误会推迟到深处变成一句与配置无关的 ``AttributeError``
        （例如 ``'NoneType' object has no attribute 'token'``）。

        Args:
            config_key: 配置键

        Returns:
            配置对象

        Raises:
            ConfigError: 配置键不存在或值为 ``None``
        """
        value = self.config.get_config(config_key)
        if value is None:
            raise ConfigError(
                "缺少配置键 '%s'。请在 config.yaml 中添加该键，"
                "或构造 RuntimeConfig(%s=...) 时显式传入。" % (config_key, config_key)
            )
        return value

    async def aclose_all(self) -> None:
        """关闭并清空所有缓存的 API 单例.

        依次 ``await`` 每个实例的 :meth:`BaseApi.aclose`，单个实例关闭失败
        只记录日志、不影响其余实例，最后统一清空缓存。
        """
        with self._lock:
            instances = [
                inst for by_key in self._instances.values() for inst in by_key.values()
            ]
            self._instances.clear()

        for inst in instances:
            if not isinstance(inst, BaseApi):
                continue
            try:
                await inst.aclose()
            except Exception:
                _log.exception("关闭 API %s 时出错", type(inst).__name__)

        if instances:
            _log.debug("已关闭 %s 个 API 实例", len(instances))

    def clear(self) -> None:
        """清空所有缓存的 API 单例实例，主要用于测试隔离.

        只丢弃引用，不会调用 :meth:`BaseApi.aclose`。
        需要释放连接等资源时请用 :meth:`aclose_all`。
        """
        with self._lock:
            self._instances.clear()

    get = get_api
