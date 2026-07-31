"""插件私有配置的声明式校验基类."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PluginConfig(BaseModel):
    """默认只读且拒绝未知字段的插件配置模型."""

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["PluginConfig"]
