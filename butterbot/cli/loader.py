"""用户应用入口加载."""

from __future__ import annotations

import importlib
from typing import Any

from butterbot.app import BotApp

from .errors import CliError


def load_app(entrypoint: str) -> BotApp:
    """加载 ``module:attribute`` 指向的 BotApp 对象."""
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

    if not isinstance(target, BotApp):
        raise CliError("应用入口 '%s' 没有提供 BotApp 实例" % entrypoint)
    return target
