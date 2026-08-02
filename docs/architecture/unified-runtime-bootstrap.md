---
title: 统一运行时装配设计
---

# 统一运行时装配设计

> 状态: 已实现 (2026-08-02).
>
> 落地版本: 3.1.0b1 Beta 线.

## 1. 核心决策

CLI 和直接运行必须共享一条装配路线:

```text
构造完整 RuntimeConfig
  -> 注入 BotApp
  -> 补全 Source 和应用基础设施
  -> 根据 config.plugin_enabled 决定是否导入插件运行时
  -> 启动统一生命周期
```

本设计确认以下约束:

1. 环境覆盖完成后的 `plugins.enabled` 是应用运行时唯一插件总开关.
2. `plugins.enabled=false` 时, 框架控制的应用启动路径不得导入任何
   `butterbot.plugin` 模块, 不得扫描候选, 也不得创建空插件管理器.
3. CLI 必须先构造完整 `RuntimeConfig`, 再把配置注入用户应用工厂.
4. `BotApp` 收到配置后统一补全基础设施和 YAML Source, CLI 不参与内部 registry
   装配.
5. `SourceFactoryRegistry` 降为 app runtime 内部实现, 不再注入用户应用工厂.
6. 插件不得注册配置 builder, Source factory 或 Source 实例.
7. `@configure + ConfigRegistrar` 扩展路线弃用并在 clean break 中删除.
8. 新的 Source 自动注册机制留给后续设计, 不在本提案中展开.
9. CLI 是普通用户首选入口. 高级开发者可以控制配置, 日志, 信号和 event loop,
   将应用嵌入其他项目.
10. `BotApp` 公开只读的 `plugin_enabled` 和 `cli_mode` 状态.
11. `core` 保持插件无关. 运行时装配属于 `app`, 不能让 core 导入 plugin, CLI 或
    adapter 实现.
12. 官方 CLI 入口只使用具名同步工厂.

## 2. 实现前问题

落地前的实现存在两套不一致路线:

- `butterbot run` 总是导入 `PluginBootstrap`, 即使插件关闭也会绑定空 manager;
- 直接 `BotApp().run()` 不经过 bootstrap, YAML 中的插件开关不会生效;
- CLI 工厂需要接收 `SourceFactoryRegistry`, 暴露框架装配细节;
- app 为使用 `SourceRef` 导入 `butterbot.plugin.contracts`, 关闭插件仍有导入成本;
- 插件 `@configure` 可以改变配置 builder 和 Source factory, 使 RuntimeConfig 构造
  依赖插件导入;
- 已构造对象入口会在 CLI 解析配置路径前加载配置, 破坏统一顺序.

新设计直接删除这些双轨和反向依赖, 不增加兼容 wrapper.

## 3. 零插件导入保证

### 3.1 保证范围

当最终配置为 `plugins.enabled=false` 时, 以下框架控制路径不得导入
`butterbot.plugin`:

- `butterbot run`;
- `BotApp(...).run()`;
- `await app.start()`;
- `async with app`.

初始化, 运行和关闭完成后应满足:

```python
assert not any(
    name == "butterbot.plugin" or name.startswith("butterbot.plugin.")
    for name in sys.modules
)
```

该保证不覆盖用户代码的主动导入. 如果用户入口模块自己执行
`import butterbot.plugin`, 框架不能撤销该行为.

### 3.2 显式插件命令

`butterbot plugin list/check/config` 是用户主动发起的插件管理操作, 允许导入
ButterBot 自身的插件工具模块. 这不属于应用运行路径的零导入保证.

允许导入不等于允许产生运行时副作用. 插件管理命令必须遵守:

- 由当前 YAML 配置驱动, 不建立另一套内存配置;
- 不构造 `BotApp`;
- 不创建 `PluginManager`;
- 不执行插件 register/start/stop/aclose;
- 不创建 Source, task, thread, session 或网络连接;
- 不修改全局 builder/factory registry;
- `list` 和 `check` 只读;
- `config` 是唯一写操作, 且只原子修改指定 YAML;
- 命令退出后不留下受管资源或进程级状态.

具体行为:

| 命令 | 插件工具导入 | 候选插件代码导入 | 可写状态 |
| --- | --- | --- | --- |
| `plugin list` | 是 | 否, 只读 entry point 元数据和 manifest | 无 |
| `plugin check` | 是 | 仅当现有配置启用且候选在 `plugin_list` 中 | 无 |
| `plugin config` | 是 | 否 | 仅指定 YAML |

`plugin check` 应在短生命周期子进程中执行候选代码校验, 避免候选 import 或构造污染
CLI 主进程的 `sys.modules`, logger, 环境变量和全局注册表. 进程隔离不能阻止恶意插件
主动写文件或访问网络, 因此插件仍属于可信代码; 插件契约必须禁止 import 和构造阶段
执行外部 I/O 或启动后台资源.

## 4. 模块边界

### 4.1 SourceRef 移入 core

`SourceRef` 是 Source 路由值对象, 不是插件控制面. 它应移动到中立位置:

```text
butterbot.core.routing.SourceRef
                 ^
                 |
      app/source_manager/source_catalog
                 |
                 +---- plugin 启用后复用
```

插件作者仍可从 `butterbot.plugin` 导入 `SourceRef`, 但这是插件包对 core 类型的导出.
关闭插件时 app 只导入 core, 不触发 Python 对 `butterbot.plugin.__init__` 的加载.

### 4.2 App 持有可选运行时协议

`BotApp` 依赖 app 内部协议, 不在模块顶层引用 `PluginManager`:

```python
class _OptionalRuntime(Protocol):
    async def register(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def aclose(self) -> None: ...
```

只有 `plugin_enabled=true` 分支才通过 `importlib.import_module()` 获取插件运行时工厂.
关闭插件时 `_optional_runtime` 保持 `None`, 不创建空对象模拟插件生命周期.

### 4.3 CLI 延迟导入插件工具

CLI 通用模块不能在顶层导入 `PluginError`, `plugin_tools` 或
`butterbot.plugin._internal`. 通用异常出口捕获 core 的 `ButterError`. 只有执行
`plugin` 子命令或运行时配置明确启用插件时才导入插件模块.

## 5. RuntimeConfig 成为完整输入

取消插件 builder 后, `RuntimeConfig.from_yaml()` 可以一次完成配置构造, 不再需要
"插件配置阶段 -> RuntimeConfig"的循环.

它负责:

1. 读取 YAML;
2. 合并声明环境和进程环境;
3. 展开 `${NAME}` 与分层环境变量覆盖;
4. 校验顶层和 `sources` 通用结构;
5. 构造内置 adapter 配置;
6. 冻结 Source definition 与构造参数;
7. 读取 `plugins.enabled` 和插件声明;
8. 暴露只读 `plugin_enabled`.

这一阶段不能:

- 导入 `butterbot.plugin`;
- 枚举插件候选;
- 执行插件代码;
- 实例化 Source;
- 创建 task, thread 或网络资源.

`plugins.enabled` 必须在环境覆盖完成后取值. 例如
`BUTTERBOT__PLUGINS__ENABLED=false` 必须在任何插件模块导入前生效.

插件专属配置可以作为不可变原始映射保存在 `RuntimeConfig`, 仅在插件启用后交给插件
运行时做完整校验. 关闭插件时只要求 `plugins` 是 mapping 且 `enabled` 是 bool,
其余字段可以保留, 方便用户先编辑配置再开启总开关.

## 6. 弃用插件配置和 Source 注册

以下模式应删除:

```python
@configure
def configure_source(self, registrar: ConfigRegistrar) -> None:
    registrar.register_builder("example", dict)
    registrar.register_factory(
        "example",
        FeedSource,
        factory_id="source",
    )
```

原因:

- 插件不应决定应用有哪些 Source;
- 插件 import/configure 不应构造或引用具体 Source 实现;
- Source 所有权应由应用配置和独立 Source 装配机制负责;
- 插件动态修改 builder/factory 会让配置构造依赖插件导入;
- 该模式妨碍 `plugins.enabled=false` 的零插件导入保证.

本次收敛应删除或内部化:

- `@configure`;
- `ConfigRegistrar` 作者 API;
- `register_builder()` 和 `register_factory()` 的插件路径;
- 插件 Source factory 所有权登记;
- 插件通过 registrar 创建, 接管或 adopt Source 的能力;
- 依赖上述能力的 source-only/combined fixture.

插件职责收窄为:

- 声明 descriptor 和依赖;
- 读取自身只读配置;
- 注册 Handler 或其他无 Source 所有权的行为;
- 在 `on_start` / `on_stop` 管理自身非 Source 资源;
- 通过稳定查询接口使用应用已经注册的能力.

未来可以设计独立的 Source 自动注册器, 负责 Source provider 发现, 配置 schema 和
所有权. 它与插件系统正交, 也不同于当前 `kwarg` 自动实例化. 本文只保留这个扩展点,
不提前定义 API, entry point 或生命周期.

## 7. 配置注入后的基础设施补全

`BotApp` 收到完整 `RuntimeConfig` 后执行唯一 assembler:

```text
RuntimeConfig
  -> 创建 AppContext / EventBus / ApiRegistry
  -> 创建内部 SourceFactoryRegistry
  -> 基于 source_definitions 自动实例化并登记内置 Source
  -> 检查 config.plugin_enabled
       false -> optional runtime 保持 None
       true  -> 动态导入插件运行时
                -> 按 config 索引并加载选中插件
                -> 校验插件配置和依赖
                -> 绑定 Handler 与生命周期
  -> PREPARED
```

内部 Source factory registry 只包含框架认可的内置 Source. 高级开发者仍可使用
`app.add_source()` 手动增加 Source. 其他自动发现需求等待后续 Source 自动注册器.

准备失败必须原子回滚:

- 删除已经添加但未启动的 Source;
- 关闭已经创建的 adapter 对象;
- 回滚插件 Handler 和上下文绑定;
- 释放日志 lease;
- 不留下全局 registry 修改.

插件初始化失败不能自动降级为无插件运行. 当 `plugin_enabled=true` 时, 配置或插件错误
必须让应用准备失败.

## 8. BotApp 对外契约

已落地的构造签名:

```python
BotApp(
    config: RuntimeConfig | None = None,
    *,
    config_path: str | Path | None = None,
    cli_mode: bool = True,
    logging_mode: Literal["managed", "external"] = "managed",
    close_timeout: float = 5.0,
    max_pending_callbacks: int | None = None,
    ctx: AppContext | None = None,
)
```

规则:

- 传入 `config` 时直接补全基础设施;
- 未传 `config` 时执行
  `RuntimeConfig.from_yaml(config_path or "config.yaml")`;
- 同时传入 `config` 和 `config_path` 抛出 `ValueError`;
- 不再公开 `source_factory_registry` 参数;
- `plugin_enabled` 只能来自最终配置;
- `cli_mode` 默认 `True`, 只描述执行宿主, 不决定插件开关;
- 配置, 运行模式和插件开关在准备完成后不可修改.

公开只读属性:

```python
@property
def plugin_enabled(self) -> bool: ...

@property
def cli_mode(self) -> bool: ...
```

`plugin_enabled` 表示配置意图和成功准备状态. 为 `False` 时 optional runtime 必须为
`None`. 为 `True` 但插件准备失败时, 构造或首次 prepare 直接抛错.

### 8.1 run 参数

配置和 `cli_mode` 应在构造期确定, 不能只放在 `run()`, 因为
`await app.start()` 和 `async with app` 必须共享同一条装配路线.

`run()` 只接收执行阶段参数:

```python
app.run(
    duration: float | None = None,
    *,
    install_signal_handlers: bool | None = None,
    health_reporter: Callable[[AppHealth], None] | None = None,
    health_interval: float = 1.0,
)
```

默认:

- `install_signal_handlers=None` 时使用 `cli_mode`;
- CLI 模式默认处理 `SIGINT` 和 `SIGTERM`;
- 嵌入模式默认不修改宿主 signal handler;
- `health_reporter=None` 时不创建健康报告 task;
- `duration=None` 时持续运行;
- `health_interval=1.0`.

`run()` 是同步阻塞入口. 默认 `duration=None` 时不会自行返回, 只有收到受支持的停止
信号, 发生 `KeyboardInterrupt`, 抛出未处理异常或外部终止进程才会结束. 只有明确
需要限时运行时才传入 `duration`; CLI 服务进程保持默认值.

嵌入已有 asyncio 应用时应使用 `await app.start()` / `await app.close()` 或
`async with app`, 不在已有 loop 中调用基于 `asyncio.run()` 的 `app.run()`.

## 9. CLI 启动路线

CLI 只负责命令参数, 进程状态和配置路径:

```text
butterbot run
  -> 解析 CLI 参数, 不导入 plugin
  -> RuntimeConfig.from_yaml(resolved_config_path)
  -> 导入用户应用工厂
  -> application(config=config, cli_mode=True)
  -> BotApp 补全基础设施
       -> plugin_enabled=false: 不导入 plugin
       -> plugin_enabled=true: 按 config 动态导入 plugin
  -> 登记 CLI RuntimeState
  -> app.run(health_reporter=...)
  -> finally 标记停止
```

官方应用入口统一为具名同步工厂:

```python
from butterbot.app import BotApp, RuntimeConfig


def app(*, config: RuntimeConfig, cli_mode: bool = True) -> BotApp:
    return BotApp(config=config, cli_mode=cli_mode)
```

CLI 不再注入 `SourceFactoryRegistry`. CLI loader, 官方文档和脚手架只接受并展示
符合签名的具名同步工厂.

后台启动只改变进程边界, 子进程继续执行同一条前台装配路线.

## 10. 直接运行与嵌入

### 10.1 开发者准备配置

```python
from butterbot.app import BotApp, RuntimeConfig

config = RuntimeConfig.from_yaml("deploy/config.production.yaml")
app = BotApp(
    config=config,
    cli_mode=False,
    logging_mode="external",
)

app.run(install_signal_handlers=False)
```

### 10.2 框架读取 YAML

```python
from butterbot.app import BotApp

app = BotApp(
    config_path="deploy/config.production.yaml",
    cli_mode=False,
)
app.run()
```

### 10.3 嵌入现有 event loop

```python
app = BotApp(
    config=config,
    cli_mode=False,
    logging_mode="external",
)

async with app:
    await host_shutdown_event.wait()
```

三种用法使用同一条 Source 和可选插件装配路线. `cli_mode=False` 不会关闭 YAML
插件功能, 是否启用只取决于 `config.plugin_enabled`.

## 11. 插件运行时约束

插件运行时导入必须完全由配置驱动:

1. 只有 `plugin_enabled=true` 才导入插件框架;
2. 只加载当前 `plugin_list` 选中的候选;
3. 不因目录存在或 distribution 已安装而自动启用;
4. import 和插件对象构造阶段必须无外部副作用;
5. Handler 注册发生在 Source 启动前;
6. `on_start` 只在全部 Source ready 后执行;
7. `on_stop` 和插件资源清理先于 Source 关闭;
8. 插件不能创建或接管 Source;
9. 插件不能修改 RuntimeConfig 或 YAML;
10. 配置修改只能由显式 CLI config 操作原子写回 YAML, 运行时只读.

插件加载错误必须包含 plugin ID, 阶段和错误类型, 但不能把 secret 或完整私有配置写入
日志和 CLI 状态.

## 12. 基础设施状态

`BotApp` 使用以下私有装配状态:

```text
NEW -> PREPARING -> PREPARED -> RUNNING -> CLOSING -> CLOSED
                    |
                    +-> PREPARE_FAILED
```

要求:

- Source 自动注册只执行一次;
- `start()`, `run()` 和 `__aenter__()` 共用 `_ensure_prepared()`;
- 准备失败撤销 Source, 插件绑定, 日志 lease 和内部 registry;
- `PREPARE_FAILED` 实例不可再次启动;
- `close()` 对已准备但未启动的应用仍完整释放资源;
- 禁用插件分支不能创建空 manager;
- 一个应用只能持有一个可选插件运行时.

## 13. 已完成的迁移

落地结果:

1. [x] 将 `SourceRef` 移入 core, 清除 app 对 plugin 的静态导入;
2. [x] 让 `RuntimeConfig` 保存最终 `plugin_enabled` 和只读插件声明;
3. [x] 删除插件 `@configure`, `ConfigRegistrar` 和 builder/factory 扩展路径;
4. [x] 删除插件 Source 创建, adopt 和 owner factory 路径;
5. [x] 把 `SourceFactoryRegistry` 降为 app runtime 内部实现;
6. [x] 新增统一 assembler 和准备状态;
7. [x] 根据 config 动态导入可选插件运行时;
8. [x] 修改 CLI 为"先 RuntimeConfig, 后应用工厂";
9. [x] 将 CLI loader 收敛为只接受具名同步工厂;
10. [x] 延迟导入 CLI 插件工具和异常;
11. [x] 让 `plugin check` 使用隔离子进程;
12. [x] 增加 `plugin_enabled`, `cli_mode` 和 run 执行参数;
13. [x] 重写 Handler 插件 fixtures, 删除 source-only/combined 插件模式;
14. [x] 更新 examples、配置指南、API 文档和稳定性 snapshot.

## 14. 验收标准

### 14.1 零导入

在全新 Python 子进程中, 为禁用插件的 CLI 和直接运行路径安装 import guard. 任何
`butterbot.plugin` 导入立即失败. 两条路线仍必须完成 Source 启动和关闭.

同时断言:

```python
assert app.plugin_enabled is False
assert app._optional_runtime is None
```

### 14.2 路线一致

同一份 RuntimeConfig 经 CLI 工厂和直接 `BotApp` 构造后得到相同的:

- Source catalog;
- Source 启动和关闭顺序;
- 插件启用判断;
- 缺少 adapter extra 时的错误;
- 失败回滚结果.

### 14.3 插件命令纯度

验证:

- `plugin list/check` 不修改 YAML, 环境变量, logger 和全局 registry;
- `plugin config` 只原子修改目标 YAML;
- 关闭总开关时不加载任何候选插件代码;
- `check` 子进程退出后主进程没有新增候选模块;
- 命令结束后无 task, thread, session 或子进程残留;
- plugin 模块 import 不安装 handler, 不创建 Source, 不启动生命周期.

### 14.4 启用插件

重写后的外部 Handler 插件 wheel 和本地目录插件 fixture 覆盖:

- 配置驱动的候选选择;
- Handler 注册;
- 依赖顺序;
- 注册失败回滚;
- Source 启动失败时插件回滚;
- 幂等关闭;
- 插件没有 Source 所有权.

### 14.5 嵌入模式

覆盖:

- `cli_mode=False` 默认不安装 signal handler;
- `logging_mode="external"` 不修改宿主 logger;
- 用户注入 RuntimeConfig;
- 框架按 `config_path` 加载 RuntimeConfig;
- 已有 event loop 中使用异步上下文;
- 两个应用不共享插件或内部 Source registry.

## 15. 最终判断

删除插件 builder/factory 注册后, 该方案的生命周期线更简单:

```text
最终配置
  -> 应用自己的 Source
  -> 配置允许时才导入插件行为
  -> 统一启动与关闭
```

`cli_mode` 只表达宿主和执行权限, `plugin_enabled` 只表达配置决策. 插件命令可以导入
插件工具, 但只能读取或原子修改 YAML, 不能借管理命令启动运行时能力. Source provider
留给独立自动注册机制, 不再借插件配置阶段间接实现.
