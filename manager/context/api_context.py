from typing import Type, Dict, Any
from .config import RuntimeConfig
from base_cls import BaseApiT


class APIContext:
    """API上下文管理，负责管理 API 单例和配置."""

    def __init__(self, config: RuntimeConfig):
        """初始化 APIContext 实例.
        Args:
            config (RuntimeConfig): 运行时API配置实例
        """
        self.config = config

    def get_api(self, cls: Type[BaseApiT]) -> BaseApiT:
        """获取API实例
        Args:
            cls (Type[BaseApiT]): API类类型
        Returns:
            BaseApiT: API实例
        """
        return cls.create(self)

    get = get_api
