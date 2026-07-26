# 生命周期与错误处理

本文覆盖 `BotApp` 从启动到关闭的完整闭环：启动失败会怎样、关闭时按什么顺序释放资源、
运行期如何动态增删事件源、以及框架抛出的异常该怎么接。

------

## 1. 三种启动方式

```python
from bilipy_bot.app import BotApp, RuntimeConfig

app = BotApp(RuntimeConfig.from_yaml())
source = app.add_source(MySource)

@app.subscribe(source.uuid, MyType.ALL)
async def handler(event):
    ...
```

| 方式 | 写法 | 适用场景 |
|---|---|---|
| 阻塞入口（推荐） | `app.run()` / `app.run(duration=300)` | 大多数场景，自带信号处理 |
| 异步上下文管理器 | `async with app: ...` | 已经在自己的协程里，需要和别的任务并跑 |
| 手动 | `await app.start()` / `await app.close()` | 需要精细控制启动与关闭时机 |

> `await app.start()` **不阻塞** —— 它只是启动所有事件源就返回。
> 直接 `asyncio.run(app.start())` 会让进程立刻退出，请用上面三种之一。

------

## 2. 启动：失败不留半启动状态

`BotApp.start()` 依次启动所有事件源。任一事件源的 `on_start()` 抛异常时：

1. 该事件源自身的 `running` 回滚为 `False`（`BaseSource.start()` 模板方法负责）；
2. **本轮已经成功启动的事件源被逐个 `stop()` 回滚**；
3. 全部失败聚合成一个 `SourceStartError` 抛出，`app.running` 保持 `False`。

```python
from bilipy_bot.app import BotApp, SourceStartError

try:
    app.run()
except SourceStartError as e:
    for name, exc in e.failures.items():
        print("启动失败:", name, "→", exc)   # 原始异常对象，不是字符串
```

这样做的原因是：应用要么整体启动成功，要么整体没启动。否则 `app.running` 为 `True`
却有一半事件源根本没跑起来，后续的 `stop()` 又会去清理从未建立的资源。

------

## 3. 关闭：固定的三步顺序

`await app.close()`（`async with` 退出和 `app.run()` 返回时都会自动调用）的顺序是固定的，
**不能调换**：

```
1. SourceManager.close()      停止全部事件源、清空注册
      ↓  先停源，总线才不会在排空期间又收到新事件
2. EventBus.close(timeout)    排空正在执行的订阅回调
      ↓  先排空回调，回调里才不会用到下一步已经关掉的 API
3. ApiRegistry.aclose_all()   释放各 API 持有的连接与后台任务
```

即使第 1 步因取消而抛出，后两步仍会在 `finally` 中完成。

### 回调排空（drain）

`EventBus.close()` 会等待所有 in-flight 回调真正跑完，最长 `close_timeout` 秒
（默认 5 秒，构造时可调）：

```python
app = BotApp(config, close_timeout=10.0)
```

超时未完成的回调会被 `cancel()` 并 `await` 到真正结束。不做排空的后果是进程退出时
pending 回调被 GC，Python 打印 `Task was destroyed but it is pending!`，
用户回调执行到一半被掐断。

关闭后的总线不再派发事件：`publish` 只记录一条警告然后丢弃，
避免在排空过程中又派生出新回调。

### 让自己的 API 参与关闭

`BaseApi.aclose()` 默认是空实现。持有长连接或后台任务的 API 覆写它即可：

```python
class MyApi(BaseApi):
    async def aclose(self) -> None:
        """必须幂等；抛出的异常会被记录后忽略，不影响其他 API 的关闭。"""
        await self._client.stop()
```

------

## 4. 信号处理：Ctrl+C 与 SIGTERM

`app.run()` 会为 `SIGINT`（Ctrl+C）和 `SIGTERM`（`docker stop`、k8s 缩容）
注册处理器，两者都走**正常退出路径**——跳出等待后执行完整的 `close()`。

只依赖 `KeyboardInterrupt` 是不够的：容器里收到的是 SIGTERM，进程会被直接杀掉，
清理代码一行都不会执行。

不支持 `add_signal_handler` 的平台（如 Windows 的 ProactorEventLoop）会自动回退到
`KeyboardInterrupt` 行为。

停止过程中若某个事件源的 `stop()` 抛出 `CancelledError`，框架会**先清理完其余事件源**，
最后再把取消向上重抛——`CancelledError` 不是 `Exception` 的子类，
不单独接住就会中断后面所有事件源的清理。

------

## 5. 运行期动态增删事件源

运行中新增事件源的顺序是 **注册 → 订阅 → 启动**，三步都要显式做：

```python
async with app:
    source = app.add_source(MySource)          # 1. 注册（已自动注入 ctx）

    @app.subscribe(source.uuid, MyType.ALL)    # 2. 订阅
    async def handler(event):
        ...

    await app.start_source(source)             # 3. 启动
```

`add_source` **不会**自动启动，即使应用已在运行。因为自动启动会让事件在 `subscribe`
注册完成前就开始产生，那些事件会被静默丢掉。

| 方法 | 作用 |
|---|---|
| `app.add_source(cls, **kw)` | 注册事件源（运行中会立即注入 `ctx`） |
| `await app.start_source(src)` | 启动单个事件源（幂等，接受实例或 UUID） |
| `await app.stop_source(src)` | 停止单个事件源，**保留**注册与订阅，可再次启动 |
| `await app.remove_source(uuid)` | 停止 → 清理其全部订阅 → 摘除注册 |
| `app.unsubscribe(uuid)` | 只清理订阅，返回被移除的回调数量 |

> `remove_source` 是 `async` 的：它需要先 `await source.stop()`。
> 只 pop 不停止会留下"幽灵源"——后台任务还在跑，派发表里的回调永久残留，
> 而且同一 UUID 的新事件源会意外继承旧订阅。

------

## 6. 异常层级

所有框架主动抛出的异常都继承 `BilipyError`，可以从 `bilipy_bot.app` 直接导入：

```
BilipyError                     框架异常基类
├── ConfigError        (+ValueError)    配置文件格式错误、配置项构建失败、必需配置键缺失
├── LifecycleError     (+RuntimeError)  在已关闭的对象上继续操作
├── SubscriptionError  (+ValueError)    订阅规则在 supported_types 中无任何匹配
├── ApiError                            API 构建或调用错误
└── SourceError                         事件源相关错误
    └── SourceStartError                一个或多个事件源启动失败（含 .failures）
```

括号里是同时继承的内置异常——既能被新类型精确捕获，也不会让原本
`except ValueError` / `except RuntimeError` 的调用方漏掉。

```python
from bilipy_bot.app import BilipyError, ConfigError

try:
    app = BotApp()
    app.run()
except ConfigError as e:
    print("配置有问题:", e)      # 例如「缺少配置键 'napcat'」
except BilipyError as e:
    print("框架错误:", e)
```

### 两个从"静默"改成"报错"的行为

**订阅规则无匹配**会抛 `SubscriptionError`，而不是记一条警告后丢掉：

```python
@app.subscribe(source.uuid, r"napcat\.mesage")   # 拼错了
async def handler(event): ...
# SubscriptionError: 订阅规则 'napcat\\.mesage' 在 NapcatType 中无匹配的具体状态，
# 该订阅永远不会触发。可用的状态值：['napcat.all', 'napcat.message', ...]
```

这种订阅永远不会触发，几乎总是状态值或正则写错了。静默丢弃会让人面对"回调不执行"
却无从下手。

**必需配置缺失**会抛 `ConfigError`。在自己的 API 里用 `require_config` 取必需配置：

```python
class MyApi(BaseApi):
    @classmethod
    def create(cls, ctx, config_key):
        return cls(ctx.require_config(config_key))   # 缺失 → ConfigError
        # 而不是 ctx.config.get_config(config_key)   # 缺失 → 静默 None
```

用 `get_config` 时缺失的键会静默返回 `None`，错误被推迟到深处变成一句与配置毫无关系的
`AttributeError: 'NoneType' object has no attribute 'token'`。
配置本就可选时（如 B 站的匿名访问）才应该用 `get_config`。

------

## 7. 参考实现

- `bilipy_bot/app/bot_app.py` — `close()` 全序、`run()` 信号处理
- `bilipy_bot/app/source_manager.py` — 启动回滚、动态增删、取消态清理
- `bilipy_bot/core/event/event_bus.py` — `close()` 排空、`remove_subscribers`
- `bilipy_bot/core/exceptions.py` — 异常层级
- 测试：`tests/app/test_bot_app.py`、`tests/app/test_source_manager.py`、
  `tests/core/event/test_event_bus_close.py`、`tests/core/source/test_base_source.py`
