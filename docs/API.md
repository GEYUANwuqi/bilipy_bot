# 如何适配一个 API

本章将介绍如何基于 `BaseApi` 基类适配一个 API 模块。

------

## 基类说明

```python
class BaseApi(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @classmethod
    @abstractmethod
    def create(cls, ctx: "APIContext", config_key: str) -> Self:
        """API实例工厂方法"""
        pass

BaseApiT = TypeVar("BaseApiT", bound=BaseApi)
```

`BaseApi` 定义了一个工厂方法 `create`，用于在运行时动态创建 API 实例。

- `ctx`：运行时上下文，可以从中获取配置信息（如 cookie、token 等）
- `config_key`：配置键，用于从上下文中获取对应的配置项
- 同一配置键对应单个实例（单例模式）

> 注：通过全局使用一个配置键可以实现全局单例，但是提供了多配置的能力

------

## 适配步骤

### 1. 定义配置类

首先定义 API 所需的配置类：

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MyApiConfig:
    """MyApi 配置

    Attributes:
        url: API 地址
        token: 认证 Token（可选）
    """
    url: str
    token: Optional[str] = None
```

### 2. 实现 API 类

继承 `BaseApi` 并实现必要的方法：

```python
from bilipy_bot.app.api import BaseApi
from bilipy_bot.app.context import APIContext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bilipy_bot.app.context import APIContext

class MyApi(BaseApi):
    """MyApi 实现"""

    @classmethod
    def create(cls, ctx: "APIContext", config_key: str = "my_api") -> "MyApi":
        """
        从上下文创建 MyApi 实例
        Args:
            ctx: API 上下文
            config_key: 配置键
        """
        config = ctx.config.get_config(config_key)
        return cls(config)

    def __init__(self, config: MyApiConfig):
        """初始化 MyApi 客户端
        Args:
            config: MyApi 配置
        """
        self.config = config
        # 初始化其他资源...

    async def start(self):
        """启动客户端"""
        # 建立连接等初始化操作
        pass

    async def stop(self):
        """停止客户端"""
        # 清理资源
        pass

    # ================== 业务接口 ================== #

    async def get_data(self, id: int) -> dict:
        """获取数据的示例接口"""
        # 实现业务逻辑
        pass
```

------

## 完整示例

以下是一个完整的 API 适配示例，参考 [napcat_api](../bilipy_bot/sources/napcat/api/napcat_api.py)：

```python
import asyncio
import json
from typing import Optional, Any, Callable, Awaitable
from logging import getLogger
from dataclasses import dataclass
from uuid import uuid4

from bilipy_bot.app.context import APIContext
from bilipy_bot.app.api import BaseApi

_log = getLogger("MyApi")


@dataclass
class MyApiConfig:
    """MyApi 配置"""
    url: str
    token: Optional[str] = None
    timeout: float = 30.0


class MyApiClient:
    """底层客户端实现"""

    def __init__(self, config: MyApiConfig):
        self.url = config.url
        self.token = config.token
        self.timeout = config.timeout
        self._handler: Optional[Callable[[dict], Awaitable[None]]] = None

    def set_handler(self, handler: Callable[[dict], Awaitable[None]]):
        """设置消息处理函数"""
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError("handler must be an async function")
        self._handler = handler

    async def start(self):
        """启动客户端"""
        # 建立连接
        pass

    async def stop(self):
        """停止客户端"""
        # 断开连接
        pass

    async def send_request(self, message: dict) -> Optional[dict]:
        """发送请求"""
        # 实现请求逻辑
        pass


class MyApi(BaseApi):
    """MyApi 实现"""

    @classmethod
    def create(cls, ctx: APIContext, config_key: str = "my_api") -> "MyApi":
        """从上下文创建 MyApi 实例"""
        config = ctx.config.get_config(config_key)
        return cls(config)

    def __init__(self, config: MyApiConfig):
        self.client = MyApiClient(config)

    def set_handler(self, handler: Callable[[dict], Awaitable[None]]):
        """设置消息处理函数"""
        self.client.set_handler(handler)

    async def start(self):
        """启动客户端"""
        await self.client.start()

    async def stop(self):
        """停止客户端"""
        await self.client.stop()

    async def send_request(self, message: dict) -> Optional[dict]:
        """发送请求到服务器"""
        return await self.client.send_request(message)

    # ================== 业务接口 ================== #

    async def get_user_info(self, user_id: int) -> Optional[dict]:
        """获取用户信息"""
        return await self.send_request({
            "action": "get_user_info",
            "params": {"user_id": user_id}
        })
```

------

## 使用方式

在事件源中使用 API：

```python
from bilipy_bot.app.source import BaseSource

class MySource(BaseSource):

    def __init__(self, config_key: str = "my_api"):
        super().__init__()
        self.config_key = config_key

    @property
    def api(self) -> MyApi:
        """获取 MyApi 实例"""
        return self.ctx.api_ctx.get(MyApi, self.config_key)

    async def start(self):
        """启动事件源"""
        await self.api.start()

    async def stop(self):
        """停止事件源"""
        await self.api.stop()
```

------

## 参考实现

- [napcat_api](../bilipy_bot/sources/napcat/api/napcat_api.py)：NapCat QQ Bot API 实现
- [bilibili_api](../bilipy_bot/sources/bilibili/api/bili_api.py)：B站 API 实现
