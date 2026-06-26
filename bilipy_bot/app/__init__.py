"""bilipy_bot 应用入口模块.

用户应该从这里导入需要的类，而不是直接从 core 导入。
"""

from bilipy_bot.core.event import Event

from .bot_app import BotApp
from .config import RuntimeConfig

__all__ = [
    # 应用主入口
    "BotApp",
    # 事件
    "Event",
    # 配置
    "RuntimeConfig",
]
