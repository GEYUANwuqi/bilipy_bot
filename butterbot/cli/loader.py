"""用户应用入口加载."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from butterbot.app import BotApp

from .errors import CliError

ApplicationEntry = BotApp | Callable[..., BotApp]


def load_application(entrypoint: str) -> ApplicationEntry:
    """加载应用入口，但把配置注入和应用构造留给 bootstrap.

    支持两种入口：
    - 已构造的 ``BotApp`` 实例（例如 ``app = BotApp()``）；
    - 同步工厂，接受 ``config`` 与 ``source_factory_registry`` 并返回 ``BotApp``。
    """
    target = resolve_entrypoint(entrypoint)
    if isinstance(target, BotApp):
        return target
    if not callable(target):
        raise CliError("应用入口 '%s' 必须是 BotApp 实例或可调用工厂" % entrypoint)
    return cast(Callable[..., BotApp], target)


def resolve_entrypoint(entrypoint: str) -> Any:
    """解析 ``module.attribute`` 或 ``module:attribute``，但不调用目标."""
    if ":" in entrypoint:
        module_name, separator, attribute_path = entrypoint.partition(":")
    else:
        module_name, separator, attribute_path = entrypoint.rpartition(".")
    if not separator or not module_name or not attribute_path:
        raise CliError("应用入口必须使用 'package.module.attribute' 格式")

    try:
        target: Any = importlib.import_module(module_name)
    except Exception as exc:
        raise CliError(
            "无法导入应用模块 '%s'（%s）" % (module_name, type(exc).__name__)
        ) from exc

    for attribute in attribute_path.split("."):
        if not attribute:
            raise CliError("应用入口包含空属性: %s" % entrypoint)
        try:
            target = getattr(target, attribute)
        except AttributeError as exc:
            raise CliError("应用入口不存在: %s" % entrypoint) from exc

    return target


__all__ = ["ApplicationEntry", "load_application", "resolve_entrypoint"]
