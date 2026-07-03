---
name: bilipy-bot-dev
description: >
  bilipy_bot 项目开发指南。当你在这个项目中编写或修改任何代码时，必须遵循此 skill。
  涵盖：项目规范（uv, pytest, ruff, pre-commit, pyright）、项目架构与目录结构、
  核心模块用法（BotApp, Event, EventBus, BaseSource, BaseType, BaseDataModel,
  BaseFilter, RuntimeConfig, AppContext, APIContext）、事件源适配步骤、
  以及"功能 + test + docs 三位一体"提交原则。
  触发场景：编写新功能、修改框架核心代码、适配新事件源、添加测试或文档、
  代码审查、询问项目规范或架构问题。
---

# bilipy_bot 开发指南

> **核心原则**：触及框架核心（`bilipy_bot/core/`, `bilipy_bot/app/`）时，
> **功能 + test + docs 三位一体**，缺一不可。
> 适配外部事件源（`bilipy_bot/sources/`）时，暂不强制 test 和 docs。

---

## 一、项目规范

### 1.1 包管理：uv

```bash
uv sync                          # 安装所有依赖（含 dev）
uv add <pkg>                     # 添加运行时依赖
uv add --dev <pkg>               # 添加开发依赖
uv run <command>                 # 在项目虚拟环境中运行命令
```

- Python 版本要求：`>=3.12`
- 使用清华源（`pyproject.toml` 中配置）

### 1.2 代码检查与格式化：ruff

```bash
uv run ruff check .              # 代码检查（lint）
uv run ruff format --check .     # 格式化检查（不写入）
uv run ruff format .             # 自动格式化
```

**ruff 配置**（`pyproject.toml`）：
- `line-length = 88`（与 black 兼容）
- 启用规则：`E`（pycodestyle errors）, `W`（pycodestyle warnings）, `F`（Pyflakes）, `I`（import 排序）
- 忽略：`E501`（行长交给 formatter）
- 格式：双引号、空格缩进、LF 换行

**import 排序规则**：标准库 → 第三方库 → 本地模块，各组之间空行分隔。

### 1.3 类型检查：pyright

```bash
uv run pyright                   # 类型检查
```

**配置**：`typeCheckingMode = "basic"`，检查范围 `bilipy_bot` 和 `tests`。

### 1.4 测试：pytest

```bash
uv run pytest                    # 运行所有测试
uv run pytest tests/core/event/  # 运行特定目录测试
uv run pytest -k "test_name"     # 按名称筛选测试
uv run pytest --cov              # 带覆盖率报告
```

- 测试目录：`tests/`
- 支持 `pytest-asyncio`（异步测试用 `@pytest.mark.asyncio`）
- 共享 fixtures 定义在 `tests/conftest.py`
- 测试文件命名：`test_<module>.py`
- 测试类命名：`Test<Subject>`
- 测试方法命名：`test_<behavior>`

### 1.5 提交前检查：pre-commit

```bash
uv run pre-commit run --all-files  # 手动运行所有 hooks
```

**hooks 列表**（`.pre-commit-config.yaml`）：
1. `ruff --fix` — 自动修复 lint 问题
2. `ruff-format` — 自动格式化
3. `trailing-whitespace` — 删除行尾空白
4. `end-of-file-fixer` — 文件末尾换行
5. `check-yaml` / `check-toml` / `check-json` — 校验配置文件语法
6. `check-merge-conflict` — 检查合并冲突标记

> 建议在提交前习惯性运行一次 `uv run pre-commit run --all-files`。

### 1.6 提交信息规范

参考最近的提交记录风格（`git log --oneline`）：
- `feat: <描述>` — 新功能
- `fix: <描述>` — 修复 bug
- `refactor: <描述>` — 重构
- `test: <描述>` — 测试相关
- `docs: <描述>` — 文档更新

---

## 二、项目架构

### 2.1 目录总览

```
bilipy_bot/
├── app/                     # 用户入口（推荐导入路径）
│   ├── bot_app.py           # BotApp：持有所有高层基础设施
│   ├── source_manager.py    # SourceManager：事件源生命周期管理
│   ├── config.py            # RuntimeConfig：键值对配置 + YAML 加载
│   └── __init__.py          # 导出 BotApp, Event, RuntimeConfig
├── core/                    # 框架核心（不建议外部直接导入）
│   ├── event/               # 事件系统：Event, EventBus, Subscriber
│   ├── source/              # BaseSource 事件源基类
│   ├── api/                 # BaseApi API 基类（工厂方法模式）
│   ├── data/                # BaseDataMixin, BaseDataModel（pydantic）
│   ├── types/               # BaseType 标签枚举（scope.state 格式）
│   ├── context/             # AppContext（DI 容器）, APIContext（API 单例池）
│   └── filter/              # BaseFilter 过滤器基类（& / | 组合）
├── sources/                 # 事件源实现
│   ├── bilibili/            # B站：动态/直播/弹幕（api → data → types → source）
│   └── napcat/              # QQ（NapCatQQ OneBot）：消息/通知/请求
├── utils/                   # 工具模块
│   ├── logging_config.py    # 彩色日志 + 文件日志 + 日志重定向
│   ├── websocket.py         # AsyncWebSocketClient / SyncWebSocketClient
│   ├── data_pair.py         # DataPair 新旧数据对
│   └── terminal.py          # Color 终端颜色常量
├── tests/                   # 测试目录（与源码结构对应）
│   ├── conftest.py          # 共享 fixtures
│   ├── app/                 # test_bot_app, test_source_manager, test_config
│   ├── core/                # event/, data/, types/, filter/, context/
│   └── utils/               # test_data_pair
├── docs/                    # 适配教程文档
│   ├── API.md, TYPE.md, DATA.md, FILTER.md, SOURCE.md
├── examples/                # 可运行的示例脚本
├── dev/                     # 开发调试脚本 + API 测试
├── pyproject.toml           # 项目元数据 + 工具配置
├── config.example.yaml      # 配置文件模板
└── CLAUDE.md                # Claude Code 项目指南
```

### 2.2 导入规范

```python
# ✅ 推荐：从 app 层导入
from bilipy_bot.app import BotApp, Event, RuntimeConfig

# ✅ 适配源时可用（公开 API）
from bilipy_bot.core.types import BaseType
from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.data import BaseDataModel, BaseDataMixin
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.filter import BaseFilter

# ❌ 避免：直接从 core 内部导入实现细节
from bilipy_bot.core.event.event_bus import EventBus  # 不推荐
```

### 2.3 各层职责

| 层 | 职责 | 导入约定 |
|---|---|---|
| `app/` | 用户入口，持有高层基础设施 | 用户代码的起点 |
| `core/` | 框架抽象（基类、协议） | 源适配时可导入基类，用户代码不应直接依赖 |
| `sources/` | 外部平台适配实现 | 按需导入具体源 |
| `utils/` | 通用工具（无框架依赖） | 任何地方都可以导入 |

---

## 三、核心模块详解

### 3.1 Event — 泛型事件容器

```python
from bilipy_bot.app import Event

# Event 是泛型类 Event[DataT]，携带 data, status, id
event = Event(data=my_data, status=MyType.MESSAGE)
# event.data   → MyData 实例
# event.status → MyType.MESSAGE
# event.id     → 自动生成的唯一 ID
```

**注意**：
- `Event` 从 `bilipy_bot.app` 导出（实际定义在 `bilipy_bot.core.event`）
- `data` 必须是 `BaseDataMixin` 子类实例
- `status` 必须是 `BaseType` 子类实例

### 3.2 BotApp — 应用主入口

```python
from bilipy_bot.app import BotApp

# 自动加载 config.yaml
app = BotApp()

# 或手动传入配置
app = BotApp(RuntimeConfig(bilibili=credential))

# 属性
app.config    # RuntimeConfig（只读）
app.bus       # EventBus
app.ctx       # AppContext
app.manager   # SourceManager
app.running   # bool
app.closed    # bool

# 推荐使用异步上下文管理器
async with app:
    # 应用在此运行
    ...
# 退出时自动 close
```

**生命周期方法**：
- `await app.start()` — 启动所有事件源
- `await app.stop()` — 停止所有事件源
- `await app.close()` — 关闭并释放所有资源

### 3.3 事件源管理

```python
# 添加事件源
source = app.add_source(SomeSource, **kwargs)
# source.uuid — 用于订阅时关联
# 建议通过类型获取而非保存返回值

# 获取事件源
source = app.get_source(SomeSource)           # 按类型（最常用）
source = app.get_source(source.uuid)          # 按 UUID
source = app.get_source(SomeSource, "key")    # 按类型 + config_key（同源多实例时）

# 移除事件源
app.remove_source(source.uuid)
```

### 3.4 事件订阅

#### 装饰器方式（推荐）

```python
@app.subscribe(source.uuid, SomeType.ALL)
async def handler(event: Event[SomeData]):
    # event.data 是强类型数据
    # event.status 可用于细分处理
    ...
```

#### 函数式注册

```python
async def callback(event: Event):
    ...

app.add_subscriber(source.uuid, callback, SomeType.ALL)
```

#### status 过滤器支持三种形式

```python
# 1. BaseType 枚举 — 最常用
@app.subscribe(source.uuid, LiveType.OPEN)

# 2. str 正则表达式 — 灵活匹配
@app.subscribe(source.uuid, r"danmaku\.(msg|gift)")

# 3. 编译好的 re.Pattern — 预编译避免重复
import re
pattern = re.compile(r"live\.(open|close)")
@app.subscribe(source.uuid, pattern)
```

**注意事项**：
- 回调函数**必须**是 `async def`，否则 EventBus 抛出 `TypeError`
- 多个订阅者可以监听同一个 source + status 组合，都会被触发
- 回调在 `asyncio.create_task` 中异步执行，不阻塞事件发布

### 3.5 EventBus 事件流

```
Source._monitor_loop()
  → 产生数据
  → EventBus.publish(uuid, Event(data, status))
    → SubscriberGroup.get_subscriber(uuid)
      → 遍历 Subscriber 列表
        → event.status.matches(subscriber.status_filter)
          → asyncio.create_task(subscriber.callback(event))
```

**关键细节**：
- 回调 task 被 `_background_tasks` set 持有强引用，防止被 GC 回收
- 回调完成后自动从 set 移除（通过 `add_done_callback`）
- 回调异常被捕获并记录日志，不影响其他订阅者

### 3.6 BaseType — 标签枚举

```python
from bilipy_bot.core.types import BaseType

class MyType(BaseType):
    ALL = "my.all"           # 通配符：state="all" 匹配同 scope 下所有状态
    MESSAGE = "my.message"   # scope="my", state="message"
    NOTICE = "my.notice"
```

**命名约定**：
- 值格式：`scope.state`（如 `dynamic.new`, `live.open`）
- `scope` 建议与事件源名称一致
- 每个 Type 类必须定义 `ALL = "<scope>.all"` 作为通配符

**匹配规则**：
```python
# 同 type + 同 scope + 同 state → True
MyType.MESSAGE.matches(MyType.MESSAGE)  # True

# 同 type + 同 scope + rule.state="all" → True（通配符）
MyType.MESSAGE.matches(MyType.ALL)      # True

# 不同 type → False
DynamicType.NEW.matches(MyType.ALL)     # False

# str 正则匹配 — 直接对 self.value 做 re.fullmatch
MyType.MESSAGE.matches(r"my\..*")       # True
```

### 3.7 BaseDataModel — 数据模型（Discriminator 自动分发）

```python
from typing import ClassVar
from bilipy_bot.core.data import BaseDataModel

class MyEvent(BaseDataModel):
    """根类：定义 discriminator_field"""
    discriminator_field: ClassVar[str] = "post_type"
    time: int
    post_type: str

class MessageEvent(MyEvent):
    """叶子：定义 discriminator_value"""
    discriminator_value: ClassVar[str] = "message"
    post_type: str = "message"
    content: str

# 自动路由到正确子类
event = MyEvent.from_dict({"post_type": "message", "time": 123, "content": "hi"})
# → MessageEvent 实例
```

**特性**：
- `model_config`: `frozen=True`（不可变），`extra="ignore"`（忽略多余字段）
- 支持多层嵌套分发：一级 `post_type` → 二级 `message_type` → 三级 `sub_type`
- `from_dict()` 自动递归分发，`from_type()` 按指定 type_value 构造
- 泛型类 `BaseDataModelT` 可用作 `Event[BaseDataModelT]`

### 3.8 BaseDataMixin — 轻量数据混入

用于不需要 pydantic 校验的简单数据类：

```python
from bilipy_bot.core.data import BaseDataMixin

class SimpleData(BaseDataMixin):
    def __init__(self, value: str):
        self.value = value
```

- 提供统一的 `__repr__`（排除 `raw_data` 属性）
- 类型变量 `BaseDataT` 用于泛型约束

### 3.9 BaseSource — 事件源基类

```python
from bilipy_bot.core.source import BaseSource

class MySource(BaseSource):
    def __init__(self, **kwargs):
        super().__init__()        # 必须调用！初始化 uuid 和 running
        self.config_key = "..."   # 指定使用的配置键

    async def start(self):
        self.running = True       # 标记运行状态
        # 启动轮询/WebSocket 等

    async def stop(self):
        self.running = False      # 标记停止
        # 清理资源：取消 Task，关闭连接

    @property
    def api(self):
        """获取 API 实例"""
        return self.ctx.api_ctx.get(MyApi, self.config_key)
```

**关键规则**：
- `__init__` 中**必须先调用 `super().__init__()`**
- `bind()` 由 `SourceManager.start()` 自动调用，**不要手动调用**
- 通过 `self.ctx.bus.publish(self.uuid, event)` 发布事件
- 通过 `self.ctx.api_ctx.get(ApiClass, self.config_key)` 获取 API 实例
- `self.ctx` 只在 `bind()` 之后可用（即 `start()` 中及之后）

### 3.10 BaseApi — API 基类

```python
from bilipy_bot.core.api import BaseApi
from bilipy_bot.core.context import APIContext

class MyApi(BaseApi):
    @classmethod
    def create(cls, ctx: APIContext, config_key: str) -> "MyApi":
        config = ctx.config.get_config(config_key)
        return cls(config)

    def __init__(self, config):
        self.config = config
```

- 使用**工厂方法模式**：`create()` 类方法从 APIContext 构建实例
- APIContext 按 `(type, config_key)` 缓存 API 单例，线程安全
- 通过 `app.get_api(ApiClass, config_key)` 或 `self.ctx.api_ctx.get()` 获取

### 3.11 BaseFilter — 组合过滤器

```python
from bilipy_bot.core.filter import BaseFilter

class MyFilter(BaseFilter):
    def check(self, event: Event) -> bool:
        return condition

# 组合使用
combined = filter_a & filter_b   # AND：两个都通过
combined = filter_a | filter_b   # OR：任一通过
```

### 3.12 RuntimeConfig — 配置管理

```python
from bilipy_bot.app import RuntimeConfig

# 方式1：YAML 自动加载（推荐）
config = RuntimeConfig.from_yaml("config.yaml")

# 方式2：手动构建
config = RuntimeConfig(bilibili=credential, napcat=napcat_config)

# 读取配置
value = config.get_config("key", default=None)
```

**YAML 加载规则**：
- `bilibili` 键 → 自动构建 `bilibili_api.Credential`
- `napcat` 键 → 自动构建 `NapcatConfig`
- 自定义键可通过 `register_builder(key, builder_func)` 注册构建器

### 3.13 日志系统

```python
from logging import getLogger
from bilipy_bot.utils import setup_logging

setup_logging("DEBUG")  # 或通过环境变量 LOG_LEVEL
_log = getLogger(__name__)
```

**环境变量**：`LOG_LEVEL`, `FILE_LOG_LEVEL`, `LOG_FILE_PATH`, `LOG_REDIRECT_RULES`
- 模块日志记录器推荐命名为模块名：`getLogger("BiliDynamicSource")`
- 不要使用已弃用的 `get_log()` 函数，直接用 `logging.getLogger()`

### 3.14 DataPair — 新旧数据对比

```python
from bilipy_bot.utils import DataPair

pair = DataPair[DynamicData]()
pair.update(new_data)            # 首次：old=new，后续：old←new, new=current
pair.get_data("old")             # 获取旧数据（浅拷贝）
pair.get_data("new")             # 获取新数据（浅拷贝）
```

常用于轮询型事件源判断状态变化（如动态新增/删除）。

---

## 四、适配事件源完整流程

按照以下 5 步适配新的事件源（参考 `docs/` 下的教程）：

### 步骤 1：定义 Type 类

```python
# sources/my_source/types/my_type.py
from bilipy_bot.core.types import BaseType

class MyType(BaseType):
    ALL = "my.all"
    MESSAGE = "my.message"
    NOTICE = "my.notice"
```

### 步骤 2：定义 Data 类

```python
# sources/my_source/data/event_data.py
from typing import ClassVar
from bilipy_bot.core.data import BaseDataModel

class MyEvent(BaseDataModel):
    discriminator_field: ClassVar[str] = "event_type"
    event_type: str
    timestamp: int

class MyMessageEvent(MyEvent):
    discriminator_value: ClassVar[str] = "message"
    content: str
```

### 步骤 3：实现 API

```python
# sources/my_source/api/my_api.py
from bilipy_bot.core.api import BaseApi

class MyApi(BaseApi):
    @classmethod
    def create(cls, ctx, config_key):
        config = ctx.config.get_config(config_key)
        return cls(config)

    def __init__(self, config): ...
    async def start(self): ...
    async def stop(self): ...
```

### 步骤 4：实现 Source

```python
# sources/my_source/source/my_source.py
from bilipy_bot.core.source import BaseSource
from bilipy_bot.core.event import Event

class MySource(BaseSource):
    def __init__(self, config_key="my_source", **kwargs):
        super().__init__()
        self.config_key = config_key

    async def start(self):
        self.running = True
        # 启动数据接收逻辑

    async def stop(self):
        self.running = False
        # 清理资源

    @property
    def api(self):
        return self.ctx.api_ctx.get(MyApi, self.config_key)
```

### 步骤 5：定义模块导出

```python
# sources/my_source/__init__.py
from .source.my_source import MySource
from .api.my_api import MyApi
from .types.my_type import MyType
```

**目录结构**：
```
sources/my_source/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── my_api.py
├── data/
│   ├── __init__.py
│   └── event_data.py
├── types/
│   ├── __init__.py
│   └── my_type.py
└── source/
    ├── __init__.py
    └── my_source.py
```

---

## 五、"三位一体"原则

### 5.1 适用范围

| 修改范围 | 功能 | test | docs | 说明 |
|---|---|---|---|---|
| `bilipy_bot/core/` | ✅ 必须 | ✅ 必须 | ✅ 必须 | 框架核心，影响所有 Source |
| `bilipy_bot/app/` | ✅ 必须 | ✅ 必须 | ✅ 必须 | 用户入口，影响所有使用者 |
| `bilipy_bot/utils/` | ✅ 必须 | ✅ 必须 | ✅ 必须 | 通用工具 |
| `bilipy_bot/sources/` | ✅ 必须 | ⚠️ 暂不要求 | ⚠️ 暂不要求 | 适配源，后续补充 |
| `tests/` | — | ✅ | — | 测试自身的维护 |
| `docs/` | — | — | ✅ | 文档的维护 |

### 5.2 Test 规范

- 测试文件放入 `tests/` 对应子目录（如 `tests/core/event/test_event_bus.py`）
- 使用 `pytest` + `pytest-asyncio`，异步测试加 `@pytest.mark.asyncio`
- 共享 fixtures 放 `tests/conftest.py`
- 测试类命名 `Test<Subject>`，测试方法命名 `test_<behavior>`
- 覆盖正常路径和边界情况

```python
# 示例：tests/core/types/test_base_type.py
class TestBaseType:
    def test_matches_same_scope_same_state(self):
        """同 scope 同 state 应匹配"""
        ...

    def test_matches_wildcard_state(self):
        """state="all" 应通配匹配"""
        ...

    def test_matches_different_type_returns_false(self):
        """不同 type 不应匹配"""
        ...
```

### 5.3 Docs 规范

- 框架核心的文档放入 `docs/` 目录
- 参考现有教程格式：基类说明 → 适配步骤 → 完整示例 → 参考实现
- 源代码模块 README 放入模块目录（如 `bilipy_bot/core/event/README.md`）
- 事件源文档放入 `bilipy_bot/sources/<name>/README.md`

---

## 六、常见开发模式和注意事项

### 6.1 在 Source 中获取 API

```python
# ✅ 正确：通过 APIContext 获取（确保单例）
@property
def api(self) -> MyApi:
    return self.ctx.api_ctx.get(MyApi, self.config_key)

# ❌ 错误：在 __init__ 中获取（此时 ctx 尚未绑定）
def __init__(self):
    self.api = self.ctx.api_ctx.get(...)  # self.ctx 是 None!
```

### 6.2 在 Source 中发布事件

```python
# 1. 构造数据
data = MyEvent.from_dict(raw_dict)

# 2. 确定状态
status = MyType.get_type(raw_dict)

# 3. 发布
event = Event(data=data, status=status)
await self.ctx.bus.publish(self.uuid, event)
```

### 6.3 轮询型 Source 模式

```python
async def start(self):
    self.running = True
    self._task = asyncio.create_task(self._monitor_loop())

async def stop(self):
    self.running = False
    if self._task and not self._task.done():
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
    self._task = None

async def _monitor_loop(self):
    while self.running:
        # 执行轮询逻辑
        await asyncio.sleep(self.poll_interval)
```

### 6.4 注意事项

1. **回调必须是 async def**：EventBus 会检查，同步函数抛出 `TypeError`
2. **不要手动调用 `bind()`**：由 `SourceManager.start()` 自动调用
3. **`super().__init__()` 必须在 Source 的 `__init__` 第一行调用**
4. **通过 `self.ctx` 访问上下文**：只在 `start()` 及之后可用
5. **轮询间隔不要低于 30 秒**：避免触发 API 频率限制
6. **日志记录器命名**：推荐以模块名为记录器名，便于日志重定向
7. **import 顺序**：遵循 ruff I 规则（标准库 → 第三方 → 本地）

---

## 七、快速参考

### 常用命令速查

| 命令 | 用途 |
|---|---|
| `uv sync` | 安装依赖 |
| `uv run ruff check .` | 代码检查 |
| `uv run ruff format .` | 自动格式化 |
| `uv run pyright` | 类型检查 |
| `uv run pytest` | 运行测试 |
| `uv run pre-commit run --all-files` | 提交前检查 |
| `uv run examples/napcat_example.py` | 运行 napcat 示例 |
| `uv run examples/manager_example.py` | 运行 B站监控示例 |

### 关键文件路径

| 文件 | 用途 |
|---|---|
| `pyproject.toml` | 项目配置 + 工具链配置 |
| `.pre-commit-config.yaml` | 提交前 hooks |
| `config.example.yaml` | 配置文件模板 |
| `CLAUDE.md` | Claude Code 项目概览 |
| `docs/` | 适配教程文档 |
| `tests/conftest.py` | 共享测试 fixtures |
| `examples/` | 可运行的示例脚本 |
