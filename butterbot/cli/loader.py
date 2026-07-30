"""用户应用入口加载."""

from __future__ import annotations

import importlib
from typing import Any, cast

from butterbot.app import BotApp
from butterbot.plugin import BotAppFactory

from .errors import CliError


def load_app(entrypoint: str) -> BotApp:
    """加载 ``module:attribute`` 指向的 BotApp 对象或零参数 factory."""
    target = resolve_entrypoint(entrypoint)
    if isinstance(target, BotApp):
        return target
    if callable(target):
        try:
            target = target()
        except Exception as exc:
            raise CliError(
                "应用 factory '%s' 执行失败（%s）" % (entrypoint, type(exc).__name__)
            ) from exc
    if not isinstance(target, BotApp):
        raise CliError("应用入口 '%s' 没有提供 BotApp 实例" % entrypoint)
    return target


def load_app_factory(entrypoint: str) -> BotAppFactory:
    """加载插件模式所需的同步应用 factory."""
    target = resolve_entrypoint(entrypoint)
    if isinstance(target, BotApp) or not callable(target):
        raise CliError("启用插件时应用入口必须是 factory，不能是已构造的 BotApp")
    return cast(BotAppFactory, target)


def resolve_entrypoint(entrypoint: str) -> Any:
    """解析 ``module:attribute``，但不调用目标."""
    module_name, separator, attribute_path = entrypoint.partition(":")
    if not separator or not module_name or not attribute_path:
        raise CliError("应用入口必须使用 'package.module:attribute' 格式")

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
