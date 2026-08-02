"""CLI 项目初始化与 YAML 原子读写."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from butterbot.core.exceptions import ConfigError

CONFIG_FILE = "config.yaml"

_INITIAL_CONFIG: dict[str, object] = {
    "environment": {},
    "plugins": {
        "enabled": True,
        "plugin_list": ["HelloPlugin"],
        "plugin_path": "./plugins",
        "lifecycle": {
            "start_timeout": 30,
            "stop_timeout": 10,
            "cleanup_timeout": 10,
            "drain_timeout": 5,
        },
    },
    # 内置 Source 使用该配置；第三方 Source 由应用工厂手动装配。
    "sources": {},
}

_APP_TEMPLATE = '''"""ButterBot 应用入口."""

from butterbot.app import BotApp, RuntimeConfig


def app(
    *,
    config: RuntimeConfig,
    cli_mode: bool = True,
) -> BotApp:
    """使用框架已完成解析的配置构建应用."""
    return BotApp(config=config, cli_mode=cli_mode)
'''

_PLUGIN_MANIFEST = """\
schema_version = 2
plugin_name = "HelloPlugin"
version = "0.1.0"
requires_core = ">=3.1.0b1,<3.2"
entry = "plugin.py"
requires_plugins = []
requires_distributions = []
"""

_PLUGIN_CODE = """from butterbot.plugin import ButterPlugin


class HelloPlugin(ButterPlugin):
    async def on_start(self) -> None:
        print("Hello from ButterBot plugin")
"""


def load_project_config(path: str | Path = CONFIG_FILE) -> dict[str, Any]:
    """读取项目 YAML，并要求顶层为 mapping."""
    resolved = Path(path).resolve()
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(
            "未找到 %s；请先运行 butterbot init" % resolved
        ) from None
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("配置文件顶层应为映射")
    return dict(raw)


def write_project_config(
    data: dict[str, Any],
    path: str | Path = CONFIG_FILE,
) -> Path:
    """把完整配置原子写回 YAML."""
    resolved = Path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(".%s.%s.tmp" % (resolved.name, uuid4().hex))
    try:
        temporary.write_text(
            yaml.safe_dump(
                data,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, resolved)
    except OSError as exc:
        raise ConfigError("无法写入配置文件: %s" % resolved) from exc
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return resolved


def initialize_project(root: str | Path = ".") -> tuple[Path, ...]:
    """在空目标上创建可直接运行的配置、业务入口和示例插件."""
    project_root = Path(root).resolve()
    config_path = project_root / CONFIG_FILE
    app_path = project_root / "app.py"
    plugin_root = project_root / "plugins" / "example.hello"
    targets = (
        config_path,
        app_path,
        plugin_root / "plugin.toml",
        plugin_root / "plugin.py",
    )
    conflicts = [path for path in targets if path.exists()]
    if conflicts:
        raise ConfigError(
            "初始化目标已存在，拒绝覆盖: %s"
            % ", ".join(str(path) for path in conflicts)
        )

    project_root.mkdir(parents=True, exist_ok=True)
    plugin_root.mkdir(parents=True, exist_ok=True)
    write_project_config(dict(_INITIAL_CONFIG), config_path)
    app_path.write_text(_APP_TEMPLATE, encoding="utf-8")
    plugin_root.joinpath("plugin.toml").write_text(
        _PLUGIN_MANIFEST,
        encoding="utf-8",
    )
    plugin_root.joinpath("plugin.py").write_text(
        _PLUGIN_CODE,
        encoding="utf-8",
    )
    return targets


__all__ = [
    "CONFIG_FILE",
    "initialize_project",
    "load_project_config",
    "write_project_config",
]
