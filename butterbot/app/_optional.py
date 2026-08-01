"""内置 adapter 可选依赖的延迟导入边界."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from butterbot.core.exceptions import ConfigError


def require_optional_module(
    module_name: str,
    *,
    extra: str,
    dependency_modules: tuple[str, ...],
) -> ModuleType:
    """导入可选模块, 缺少 adapter 依赖时返回明确安装指引."""
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if not any(
            missing == dependency or missing.startswith(dependency + ".")
            for dependency in dependency_modules
        ):
            raise
        raise ConfigError(
            "缺少 %s adapter 可选依赖, 请安装 "
            "pip install 'butterbot-python[%s]'" % (extra, extra)
        ) from exc


__all__ = ["require_optional_module"]
