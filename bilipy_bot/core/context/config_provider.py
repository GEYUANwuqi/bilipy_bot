"""core 层使用的配置契约."""

from typing import Any, Protocol


class ConfigProvider(Protocol):
    """core 组件所需的最小配置接口.

    core 只依赖按键读取配置；具体加载方式、YAML 解析和构建器注册均属于
    app 层职责。
    """

    def get_config(self, key: str, default: Any = None) -> Any:
        """返回配置值；键不存在时返回 ``default``."""
