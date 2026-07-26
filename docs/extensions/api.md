---
title: 开发 API
---

# 开发 API

## 契约

`BaseApi` 是 ABC，子类必须实现构造器和同步工厂：

```python
class MyApi(BaseApi):
    def __init__(self, config: MyConfig) -> None:
        self.config = config

    @classmethod
    def create(cls, ctx: ApiRegistry, config_key: str) -> "MyApi":
        return cls(ctx.require_config(config_key))
```

`create()` 是同步方法。需要网络连接时，在 Source 的异步 `on_start()` 中启动，
不要在工厂里运行事件循环。

## 单例键

```python
api = app.get_api(MyApi, "account_a")
```

缓存键是 `(API 类, config_key)`。同类同键返回同一实例；不同键返回不同实例。
工厂可以在创建过程中通过同一 `ApiRegistry` 获取另一个 API，内部使用可重入锁。

## 配置缺失

公共 API 需要配置时使用：

```python
config = ctx.require_config(config_key)
```

它在键缺失或值为 `None` 时抛 `ConfigError`。只有真正允许无配置的 API 才应使用
`ctx.config.get_config(config_key)`。

## 释放资源

覆写 `aclose()`：

```python
async def aclose(self) -> None:
    await self.client.stop()
```

要求：

- 可重复调用；
- 取消并等待自己创建的任务；
- 关闭连接、listener 和 pending Future；
- 尽量不抛异常。

`ApiRegistry.aclose_all()` 会对每个缓存实例调用 `aclose()`；单个失败只记录日志，
其余实例继续关闭，缓存最终清空。

## 错误边界

`ApiError` 已作为公共异常类型导出，但当前 `BaseApi` 不会自动把第三方异常包装为
`ApiError`。扩展应明确哪些第三方错误原样传播，哪些转换为稳定的领域错误，并
使用异常链保留 cause。

## 测试

至少覆盖：

- 同类同键缓存；
- 配置缺失；
- `aclose()` 幂等；
- 请求超时和取消清理；
- 一个实例关闭失败不影响其他实例。

详见[测试异步扩展](./testing.md)。
