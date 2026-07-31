"""插件基类与声明式注册装饰器."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Generic, TypeVar, cast

from .config import PluginConfig
from .context import PluginContext
from .routing import SourceRef, SubscriptionSpec

_ConfigureHook = Callable[..., object]
_Handler = Callable[..., Coroutine[Any, Any, None]]
_HookT = TypeVar("_HookT", bound=_ConfigureHook)
_HandlerT = TypeVar("_HandlerT", bound=_Handler)
_PluginConfigT = TypeVar("_PluginConfigT", bound=PluginConfig)
_CONFIGURE_ATTRIBUTE = "__butterbot_plugin_configure__"
_SUBSCRIPTIONS_ATTRIBUTE = "__butterbot_plugin_subscriptions__"


@dataclass(frozen=True, slots=True)
class _SubscriptionDeclaration:
    source_kind: str
    status: object
    event_filter: object | None
    allow_multiple: bool


class ButterPlugin(Generic[_PluginConfigT]):
    """本地目录和 distribution 插件共享的唯一用户基类.

    Handler 使用 :func:`register` 声明订阅，无需手工构造 ``SourceRef`` 或
    ``SubscriptionSpec``。生命周期只需按需覆盖 :meth:`on_start` 和
    :meth:`on_stop`。
    """

    config_model: ClassVar[type[PluginConfig] | None] = None

    @property
    def context(self) -> PluginContext:
        """返回框架绑定的窄化插件运行上下文."""
        context = getattr(self, "_plugin_context", None)
        if context is None:
            raise RuntimeError("插件上下文尚未绑定")
        return cast(PluginContext, context)

    @property
    def settings(self) -> Mapping[str, object]:
        """当前插件隔离且只读的配置 namespace."""
        try:
            return self.context.settings
        except RuntimeError:
            return MappingProxyType({})

    @property
    def config(self) -> _PluginConfigT:
        """返回声明 ``config_model`` 后通过校验的只读配置."""
        return cast(_PluginConfigT, self.context.config)

    @property
    def resource_root(self) -> Path | None:
        """本地插件资源根；distribution 插件返回 ``None``."""
        try:
            return self.context.resource_root
        except RuntimeError:
            return None

    @property
    def config_key(self) -> str | None:
        """返回显式配置的 Source 配置键；未配置时按 kind 唯一匹配."""
        try:
            return self.context.config_key
        except RuntimeError:
            return None

    def source_ref(self, source_kind: str) -> SourceRef:
        """使用当前插件的 ``config_key`` 构造逻辑 Source 引用."""
        return SourceRef(source_kind, self.config_key)

    async def on_start(self) -> None:
        """全部 Source 启动成功后执行；子类按需覆盖."""

    async def on_stop(self) -> None:
        """Source 停止前按依赖逆序执行；子类按需覆盖."""

    def _bind_context(
        self,
        plugin_id: str,
        settings: Mapping[str, object] | None,
        resource_root: Path | None,
        report_failure: Callable[[str, BaseException], None],
        *,
        plugin_name: str,
    ) -> None:
        frozen_settings = (
            MappingProxyType({})
            if settings is None
            else MappingProxyType(dict(settings))
        )
        config_model = self.config_model
        if config_model is not None and (
            not isinstance(config_model, type)
            or not issubclass(config_model, PluginConfig)
        ):
            raise TypeError("config_model 必须是 PluginConfig 子类")
        config = (
            None
            if config_model is None
            else config_model.model_validate(dict(frozen_settings))
        )
        self._plugin_context = PluginContext(
            plugin_id,
            plugin_name=plugin_name,
            settings=frozen_settings,
            config=config,
            resource_root=resource_root,
            report_failure=report_failure,
        )

    def _bind_runtime_context(
        self,
        *,
        get_source: Callable[[SourceRef], object | None],
        get_sources: Callable[[SourceRef], tuple[object, ...]],
        get_api: Callable[[type[Any], str], Any],
    ) -> None:
        self.context._bind_runtime(
            get_source=get_source,
            get_sources=get_sources,
            get_api=get_api,
        )

    def _subscription_specs(self) -> tuple[SubscriptionSpec, ...]:
        specs: list[SubscriptionSpec] = []
        for handler, declaration in iter_plugin_subscriptions(self):
            specs.append(
                SubscriptionSpec(
                    source=self.source_ref(declaration.source_kind),
                    status=cast(Any, declaration.status),
                    callback=cast(Any, handler),
                    event_filter=cast(Any, declaration.event_filter),
                    allow_multiple=declaration.allow_multiple,
                )
            )
        return tuple(specs)


def configure(method: _HookT) -> _HookT:
    """声明同步配置方法，manager 会注入 ``ConfigRegistrar``."""
    if not callable(method):
        raise TypeError("@configure 只能用于可调用对象")
    setattr(cast(Any, method), _CONFIGURE_ATTRIBUTE, True)
    return method


def register(
    source_kind: str,
    status: object,
    *,
    event_filter: object | None = None,
    allow_multiple: bool = False,
) -> Callable[[_HandlerT], _HandlerT]:
    """把异步 Handler 声明为逻辑 Source 订阅."""
    SourceRef(source_kind)
    if not isinstance(allow_multiple, bool):
        raise TypeError("allow_multiple 必须是布尔值")
    declaration = _SubscriptionDeclaration(
        source_kind=source_kind,
        status=status,
        event_filter=event_filter,
        allow_multiple=allow_multiple,
    )

    def decorate(method: _HandlerT) -> _HandlerT:
        if not inspect.iscoroutinefunction(method):
            raise TypeError("@register 只能用于 async Handler")
        existing = cast(
            tuple[_SubscriptionDeclaration, ...],
            getattr(method, _SUBSCRIPTIONS_ATTRIBUTE, ()),
        )
        declarations = list(existing)
        declarations.insert(0, declaration)
        setattr(cast(Any, method), _SUBSCRIPTIONS_ATTRIBUTE, tuple(declarations))
        return method

    return decorate


def iter_configure_hooks(plugin: ButterPlugin) -> tuple[_ConfigureHook, ...]:
    """按基类到子类、类内定义顺序返回配置方法."""
    hooks: list[_ConfigureHook] = []
    for name, member in _resolved_members(plugin).items():
        if not getattr(member, _CONFIGURE_ATTRIBUTE, False):
            continue
        hook = getattr(plugin, name)
        if not callable(hook):
            raise TypeError("@configure 只能用于实例方法")
        hooks.append(cast(_ConfigureHook, hook))
    return tuple(hooks)


def iter_plugin_subscriptions(
    plugin: ButterPlugin,
) -> tuple[tuple[_Handler, _SubscriptionDeclaration], ...]:
    """返回绑定 Handler 及其声明，继承和定义顺序与配置方法一致."""
    subscriptions: list[tuple[_Handler, _SubscriptionDeclaration]] = []
    for name, member in _resolved_members(plugin).items():
        declarations = getattr(member, _SUBSCRIPTIONS_ATTRIBUTE, ())
        if not declarations:
            continue
        handler = getattr(plugin, name)
        if not callable(handler):
            raise TypeError("@register 只能用于实例方法")
        subscriptions.extend(
            (cast(_Handler, handler), declaration) for declaration in declarations
        )
    return tuple(subscriptions)


def _resolved_members(plugin: ButterPlugin) -> dict[str, object]:
    definitions: dict[str, object] = {}
    for plugin_class in reversed(type(plugin).__mro__):
        definitions.update(vars(plugin_class))
    return definitions


__all__ = [
    "ButterPlugin",
    "configure",
    "register",
]
