from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from butterbot.app.bot_app import BotApp
from butterbot.app.config import (
    ConfigBuilderRegistry,
    RuntimeConfig,
    _load_resolved_yaml,
)
from butterbot.app.source_factory import SourceFactoryRegistry
from butterbot.core.exceptions import ConfigError
from butterbot.plugin.discovery.catalog import (
    PluginCandidate,
    PluginCatalog,
    PluginEntryPoint,
)
from butterbot.plugin.discovery.settings import PluginSettings
from butterbot.plugin.errors import PluginRegistrationError

from .manager import PluginManager

ApplicationEntry = Callable[..., BotApp]


class PluginBootstrap:
    """可信启动期插件的显式两阶段 bootstrap."""

    def __init__(
        self,
        path: str | Path = "config.yaml",
        *,
        environ: Mapping[str, str] | None = None,
        env_prefix: str = "BUTTERBOT__",
        entry_points: Iterable[PluginEntryPoint] | None = None,
        core_version: str | None = None,
    ) -> None:
        self._path = Path(path)
        self._environ = environ
        self._env_prefix = env_prefix
        self._entry_points = None if entry_points is None else tuple(entry_points)
        self._core_version = core_version
        self._resolved_data: dict[str, Any] | None = None
        self._settings: PluginSettings | None = None
        self._manager: PluginManager | None = None

    @property
    def settings(self) -> PluginSettings:
        """读取与 build 相同的插件系统设置."""
        self._load()
        assert self._settings is not None
        return self._settings

    @property
    def manager(self) -> PluginManager | None:
        """返回最近一次 build 创建的诊断控制面（尚未 build 时为 None）."""
        return self._manager

    def inspect_candidates(self) -> tuple[PluginCandidate, ...]:
        """只读索引所有来源，不导入任何插件代码."""
        _, settings = self._load()
        return PluginCatalog.index_candidates(
            entry_points=self._entry_points,
            local=settings.local,
            config_root=self._path.resolve().parent,
        )

    def discover(self) -> PluginCatalog:
        """执行与 build 相同的候选选择、导入和依赖校验."""
        _, settings = self._load()
        if not settings.enabled:
            return PluginCatalog(())
        catalog = PluginCatalog.discover(
            settings.plugin_list,
            entry_points=self._entry_points,
            local=settings.local,
            config_root=self._path.resolve().parent,
            core_version=self._core_version,
        )
        configured_ids = set(settings.config_by_plugin)
        enabled_ids = set(catalog.plugin_ids)
        unknown = sorted(configured_ids - enabled_ids)
        if unknown:
            raise ConfigError(
                "plugins.config 引用了未启用的 plugin ID: %s" % ", ".join(unknown)
            )
        return catalog

    def build(
        self,
        application: ApplicationEntry = BotApp,
    ) -> BotApp:
        """发现插件、构建配置和应用；运行阶段方法延迟到 app.start()."""
        resolved_data, settings = self._load()
        catalog = self.discover()

        builder_registry = ConfigBuilderRegistry.with_defaults()
        factory_registry = SourceFactoryRegistry.with_defaults()
        manager = PluginManager(
            catalog,
            builder_registry,
            factory_registry,
            plugin_settings=settings.config_by_plugin,
            lifecycle=settings.lifecycle,
        )
        self._manager = manager
        manager.configure()
        try:
            config = RuntimeConfig._from_resolved_data(
                resolved_data,
                builder_registry=builder_registry,
            )
            app = _call_application(
                application,
                config=config,
                source_factory_registry=factory_registry,
            )
        except BaseException:
            manager.abort_before_bind()
            raise

        manager.bind(app)
        app._attach_plugin_manager(manager)
        return app

    def _load(self) -> tuple[dict[str, Any], PluginSettings]:
        if self._resolved_data is None:
            self._resolved_data = _load_resolved_yaml(
                self._path,
                environ=self._environ,
                env_prefix=self._env_prefix,
            )
            self._settings = PluginSettings.from_mapping(self._resolved_data)
        assert self._settings is not None
        return self._resolved_data, self._settings

    def validate(
        self,
        application: ApplicationEntry = BotApp,
    ) -> None:
        """执行与 run 相同的发现和注册，但不启动外部 Source."""
        app = self.build(application)

        async def validate_and_close() -> None:
            try:
                await app._prepare_plugins()
            finally:
                await app.close()

        asyncio.run(validate_and_close())


def bootstrap_app(
    path: str | Path = "config.yaml",
    *,
    application: ApplicationEntry = BotApp,
    environ: Mapping[str, str] | None = None,
    env_prefix: str = "BUTTERBOT__",
    entry_points: Iterable[PluginEntryPoint] | None = None,
    core_version: str | None = None,
) -> BotApp:
    """构建绑定 PluginManager 的 BotApp；插件只在 app.start() 时注册."""
    return PluginBootstrap(
        path,
        environ=environ,
        env_prefix=env_prefix,
        entry_points=entry_points,
        core_version=core_version,
    ).build(application)


def validate_plugin_config(
    path: str | Path = "config.yaml",
    *,
    application: ApplicationEntry = BotApp,
    environ: Mapping[str, str] | None = None,
    env_prefix: str = "BUTTERBOT__",
    entry_points: Iterable[PluginEntryPoint] | None = None,
    core_version: str | None = None,
) -> None:
    """用与运行时相同的 bootstrap 校验插件配置和注册."""
    PluginBootstrap(
        path,
        environ=environ,
        env_prefix=env_prefix,
        entry_points=entry_points,
        core_version=core_version,
    ).validate(application)


def _call_application(
    application: ApplicationEntry,
    *,
    config: RuntimeConfig,
    source_factory_registry: SourceFactoryRegistry,
) -> BotApp:
    if not callable(application):
        raise TypeError("应用入口必须可调用")
    kwargs: dict[str, Any] = {
        "config": config,
        "source_factory_registry": source_factory_registry,
    }
    try:
        inspect.signature(application).bind(**kwargs)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "应用入口必须接受关键字参数 'config' 和 'source_factory_registry'"
        ) from exc

    try:
        app = application(**kwargs)
    except BaseException as exc:
        if not isinstance(exc, Exception):
            raise
        raise PluginRegistrationError(
            "<application>",
            "application",
            exc,
        ) from exc
    if inspect.isawaitable(app):
        if inspect.iscoroutine(app):
            app.close()
        raise ConfigError("应用入口必须是同步函数")
    if not isinstance(app, BotApp):
        raise ConfigError("应用入口必须返回 BotApp")
    return app


__all__ = [
    "PluginBootstrap",
    "bootstrap_app",
    "validate_plugin_config",
]
