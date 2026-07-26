"""butterbot — 事件驱动的机器人框架.

用户代码请从 :mod:`butterbot.app` 导入公开 API::

    from butterbot.app import BotApp, Event, RuntimeConfig
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("butterbot-python")
except PackageNotFoundError:  # 源码树内直接运行且未安装时
    __version__ = "0.0.0"

__all__ = ["__version__"]
