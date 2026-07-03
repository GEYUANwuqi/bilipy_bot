from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class RuntimeConfig:
    """运行时 API 配置类，存储和管理 API 配置信息.

    以键值对形式存储 API 配置，支持通过方法访问 API 配置项.

    支持从 YAML 配置文件加载:
    >>> config = RuntimeConfig.from_yaml("config.yaml")
    """

    def __init__(self, **configs: Any):
        """初始化 RuntimeConfig 实例.

        Args:
            **configs: 可变关键字参数，表示 API 配置项的键值对.
        """
        self._configs = configs

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取指定键的配置值.

        Args:
            key: 配置项的键.
            default: 如果键不存在时返回的默认值，默认为 None.

        Returns:
            配置项的值，如果键不存在则返回默认值.
        """
        return self._configs.get(key, default)

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> RuntimeConfig:
        """从 YAML 配置文件加载配置.

        自动将以下配置项转换为对应的类型对象:

        - ``bilibili`` → ``bilibili_api.Credential``
        - ``napcat`` → ``NapcatConfig``

        可通过 :func:`register_builder` 注册自定义类型的构建器.

        Args:
            path: YAML 配置文件路径，默认为 ``config.yaml``.

        Returns:
            RuntimeConfig 实例.

        Raises:
            FileNotFoundError: 配置文件不存在.
            yaml.YAMLError: YAML 文件格式错误.
            ValueError: YAML 文件顶层不是键值映射，或配置项构建失败.

        Example:
            ``config.yaml`` 内容::

                bilibili:
                  sessdata: ""
                  bili_jct: ""
                  buvid3: ""

                napcat:
                  url: "ws://localhost:3001"
                  token: ""
                  heartbeat: 30.0

            加载::

                config = RuntimeConfig.from_yaml()
                # 等价于:
                # config = RuntimeConfig(
                #     bilibili=Credential(sessdata="", ...),
                #     napcat=NapcatConfig(url="ws://...", ...),
                # )
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError("配置文件不存在: %s" % path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(
                "配置文件格式错误: 顶层应为映射 (dict)，实际得到 %s"
                % type(data).__name__
            )
        configs: dict[str, Any] = {}
        for key, value in data.items():
            builder = _CONFIG_BUILDERS.get(key)
            if builder is not None:
                try:
                    configs[key] = builder(value)
                except Exception as e:
                    raise ValueError("配置项 '%s' 构建失败: %s" % (key, e)) from e
            else:
                configs[key] = value
        return cls(**configs)


# ==================== 配置对象构建器 ====================

_CONFIG_BUILDERS: dict[str, Any] = {}
"""配置键到构建函数的映射.

键是 YAML 配置文件中的顶层键名，值是对应的构建函数。
构建函数接收 YAML 中该键对应的值（dict），返回构造好的配置对象。

用户可以通过 :func:`register_builder` 注册自定义构建器。
"""


def register_builder(key: str, builder: Any) -> None:
    """注册自定义配置对象构建器.

    Args:
        key: YAML 配置文件中的顶层键名.
        builder: 构建函数，接收 dict 参数，返回配置对象实例.

    Example:
        为自定义 ``my_source`` 注册构建器::

            def build_my_source(value: dict) -> MyConfig:
                return MyConfig(**value)

            register_builder("my_source", build_my_source)

            config = RuntimeConfig.from_yaml("config.yaml")
    """
    _CONFIG_BUILDERS[key] = builder


# --- 内置构建器 ---


def _build_bilibili(value: dict) -> Any:
    from bilibili_api import Credential

    return Credential(**value)


def _build_napcat(value: dict) -> Any:
    from bilipy_bot.sources.napcat.api.napcat_api import NapcatConfig

    return NapcatConfig(**value)


register_builder("bilibili", _build_bilibili)
register_builder("napcat", _build_napcat)
