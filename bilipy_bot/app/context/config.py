from typing import Any


class RuntimeConfig:
    """运行时API配置类，存储和管理API配置信息.
        以键值对形式存储API配置，支持通过方法访问API配置项.
    """
    def __init__(self, **configs):
        """初始化RuntimeConfig实例.
        Args:
            **configs: 可变关键字参数，表示API配置项的键值对.
        """
        self._configs = configs

    def get_config(self, key: str, default=None) -> Any:
        """获取指定键的配置值.
        Args:
            key: 配置项的键.
            default: 如果键不存在时返回的默认值，默认为None.
        Returns:
            配置项的值，如果键不存在则返回默认值.
        """
        return self._configs.get(key, default)
