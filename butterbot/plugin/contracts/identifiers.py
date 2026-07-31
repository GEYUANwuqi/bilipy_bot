"""插件标识符约束."""

from __future__ import annotations

import keyword
import re

from butterbot.plugin.errors import PluginCompatibilityError

PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
CAPABILITY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]*[a-z0-9])?$")


def validate_plugin_id(value: object) -> str:
    """校验并返回跨来源稳定 plugin ID."""
    validate_identifier(value, "plugin_id", PLUGIN_ID_PATTERN)
    assert isinstance(value, str)
    return value


def validate_plugin_name(value: object) -> str:
    """校验并返回与实现类名一致的插件名称."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 100
        or not value.isidentifier()
        or keyword.iskeyword(value)
    ):
        raise PluginCompatibilityError(
            "plugin_name 必须是 1-100 个字符的合法 Python 类名"
        )
    return value


def validate_identifier(
    value: object,
    label: str,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise PluginCompatibilityError(
            "%s 必须使用小写字母、数字及 '.', '_' 或 '-' 组成的稳定标识" % label
        )


def validate_unique_identifiers(
    values: object,
    label: str,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(values, tuple):
        raise PluginCompatibilityError("%s 必须是 tuple" % label)
    seen: set[str] = set()
    for value in values:
        validate_identifier(value, label, pattern)
        if value in seen:
            raise PluginCompatibilityError("%s 包含重复标识 '%s'" % (label, value))
        seen.add(value)


__all__ = [
    "CAPABILITY_PATTERN",
    "PLUGIN_ID_PATTERN",
    "validate_identifier",
    "validate_plugin_id",
    "validate_plugin_name",
    "validate_unique_identifiers",
]
