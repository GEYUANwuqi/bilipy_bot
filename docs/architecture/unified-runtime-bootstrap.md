---
title: 统一运行时装配设计
---

# 统一运行时装配设计

> 状态: 设计提案, 尚未实现.
>
> 目标版本: R1 后续收敛.

## 1. 背景

当前 CLI 与直接运行存在两套不完全一致的装配路线:

- `butterbot run` 总是导入插件 bootstrap, 即使
  `plugins.enabled=false`, 仍会创建并绑定空 `PluginManager`;
- 直接构造 `BotApp` 后调用 `app.run()` 不经过插件 bootstrap,
  YAML 中的 `plugins.enabled=true` 不会生效;
- CLI 应用工厂需要接收 `SourceFactoryRegistry`, 把框架内部装配细节暴露给用户;
- `BotApp` 和 `SourceManager` 为使用 `SourceRef` 直接导入
  `butterbot.plugin.contracts`, 所以禁用插件也不能做到零插件模块导入;
- 插件 `@configure` 可以注册配置 builder 和 Source factory, 因此当前实现必须先加载
  插件, 再构造完整 `RuntimeConfig`.

这些差异提高了用户理解成本, 也使 CLI, 直接运行和嵌入运行难以共享同一条生命周期.

## 2. 已确认的设计目标

新的运行时装配遵守以下约束:

1. YAML 经过环境变量合并后的 `plugins.enabled` 是应用运行时唯一插件总开关.
2. `plugins.enabled=false` 时, 框架控制的启动路径不得导入任何
   `butterbot.plugin` 模块, 不得扫描插件候选, 也不得创建空插件管理器.
3. CLI 和直接运行都先得到 `RuntimeConfig`, 再把配置注入 `BotApp`.
4. `BotApp` 在配置注入后统一补全基础设施, 包括配置解析完成, Source factory 汇总,
   YAML Source 自动注册和可选插件控制面.
5. `SourceFactoryRegistry` 降为运行时内部实现, 不再作为 CLI 应用工厂参数.
6. CLI 是普通用户首选入口. 高级开发者仍可自定义配置, 日志, 信号和事件循环所有权,
   将 `BotApp` 嵌入其他项目.
7. `BotApp` 公开只读的 `plugin_enabled` 和 `cli_mode` 状态.
8. `core` 继续保持插件无关. 装配属于 `app` 层, 不能让 `core` 导入 plugin, CLI 或
   adapter 实现.

## 3. 零插件导入的边界

本设计中的"零插件导入"指框架控制的应用启动路径:

- `butterbot run`;
- `BotApp(...).run()`;
- `await app.start()`;
- `async with app`.

当最终配置为 `plugins.enabled=false` 时, 上述路径结束初始化, 启动和关闭后,
`sys.modules` 中不应出现任何以 `butterbot.plugin` 开头的模块.

该保证不可能覆盖用户应用自己的显式导入. 如果入口模块主动执行
`import butterbot.plugin`, 该导入由用户代码负责, 框架不能撤销.

显式的 `butterbot plugin list/check/config` 是插件管理操作. 本提案把这些命令视为
零导入保证的例外, 因为用户已经主动要求操作插件系统. 如果要求总开关关闭时这些
命令也不得导入插件模块, 它们只能在读取基础配置后直接报告系统已关闭, 无法继续列出
或检查插件候选. 这一点需要在实现前最终确认.

## 4. 模块边界调整

### 4.1 移出通用路由契约

`SourceRef` 同时被应用和插件使用, 本质上是 Source 路由值对象, 不是插件控制面.
它应移动到中立位置, 例如 `butterbot.core.routing`:

```text
butterbot.core.routing.SourceRef
                 ^
                 |
      app/source_manager/source_catalog
                 |
                 +---- plugin 在启用后复用
```

插件作者仍可从 `butterbot.plugin` 导入 `SourceRef`, 但这是插件包对 core 类型的导出.
禁用插件的应用代码只导入 core 类型, 不再触发 Python 对
`butterbot.plugin.__init__` 的隐式加载.

### 4.2 App 层持有装配协议

`BotApp` 只依赖一个 app 内部的运行时协议, 不直接引用 `PluginManager` 类型:

```python
class _OptionalRuntime(Protocol):
    async def register(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def aclose(self) -> None: ...
```

只有 `plugin_enabled=true` 分支才通过 `importlib.import_module()` 获取插件运行时工厂.
关闭时该字段保持 `None`, 不使用空对象替代.

### 4.3 CLI 延迟导入插件命令

CLI 通用命令模块不能在顶层导入 `PluginError`, `plugin_tools` 或
`butterbot.plugin._internal`. 通用异常出口捕获 core 的 `ButterError`; 插件子命令在
真正执行时再导入自己的控制面.

## 5. RuntimeConfig 两阶段模型

### 5.1 为什么必须分两阶段

以下两个要求存在先后依赖:

1. CLI 必须先构造 `RuntimeConfig`, 才能知道 `plugins.enabled`;
2. 启用插件后, 插件 `@configure` 可以注册配置 builder, 这些 builder 又必须参与
   Source 配置构造.

如果 `RuntimeConfig.from_yaml()` 仍立即执行全部 Source builder, 它会在决定是否加载
插件前要求插件 builder 已经存在, 形成循环依赖.

### 5.2 阶段 A: 插件无关的结构化配置

`RuntimeConfig.from_yaml()` 负责:

1. 读取 YAML;
2. 合并声明环境和进程环境;
3. 展开 `${NAME}` 与分层环境变量覆盖;
4. 校验顶层, `sources`, `source_name` 和 `kwarg` 的通用结构;
5. 读取并保存 `plugins.enabled`;
6. 保存尚未经过 adapter/plugin builder 的 Source 原始配置;
7. 保存原始插件设置, 但不导入插件 schema 或插件代码.

这一阶段不能:

- 导入 `butterbot.plugin`;
- 枚举 entry point 或本地 manifest;
- 导入 Bilibili/NapCat 实现;
- 执行插件 `@configure`;
- 实例化 Source.

`plugins.enabled` 必须在环境覆盖完成后取值. 例如
`BUTTERBOT__PLUGINS__ENABLED=false` 应在任何插件模块导入前生效.

### 5.3 阶段 B: 运行时准备

`BotApp` 收到阶段 A 的配置后, 由 app 内部 assembler 执行:

1. 创建内置 builder 和 Source factory 的隔离注册表;
2. 检查 `config.plugin_enabled`;
3. 为 `false` 时直接跳过插件分支;
4. 为 `true` 时才动态导入插件运行时, 完成发现和同步 `@configure`;
5. 使用最终 builder 集合解析 Source 原始配置;
6. 生成新的已准备 `RuntimeConfig`, 不原地修改调用方注入的配置对象;
7. 创建 `AppContext`, `EventBus` 和 `SourceManager`;
8. 使用内部 Source factory registry 自动实例化 YAML Source;
9. 启用插件时绑定唯一插件运行时, 禁用时保持 `None`.

建议保留插件注册 builder 的现有能力, 但把 builder 执行从
`RuntimeConfig.from_yaml()` 延迟到阶段 B. `_prepare()` 返回新的配置实例, 避免同一个
阶段 A 配置被两个应用以不同插件集合准备时发生交叉污染.

## 6. BotApp 对外契约

建议构造签名收敛为:

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

规则如下:

- 传入 `config` 时直接进入阶段 B;
- 未传 `config` 时由框架执行
  `RuntimeConfig.from_yaml(config_path or "config.yaml")`;
- 同时传入 `config` 和 `config_path` 直接报 `ValueError`;
- `SourceFactoryRegistry` 不再是公开构造参数;
- `plugin_enabled` 来自完成环境覆盖后的配置, 不能由构造参数覆盖;
- `cli_mode` 默认 `True`, 只描述执行宿主, 不决定插件是否启用;
- 基础设施准备完成后, `plugin_enabled` 与 `cli_mode` 均为只读属性;
- 一个 `BotApp` 实例不能在运行后更换配置, 运行模式或插件开关.

建议公开:

```python
@property
def plugin_enabled(self) -> bool: ...

@property
def cli_mode(self) -> bool: ...
```

`plugin_enabled` 表示配置意图. 当它为 `False` 时插件运行时必须为 `None`; 当它为
`True` 但插件初始化失败时, 应用构造失败, 不能留下"开关为真但继续无插件运行"的
降级状态.

### 6.1 run 参数

配置, `cli_mode` 和基础设施所有权应在构造期确定, 不建议只放进 `run()`. 原因是
`await app.start()` 和 `async with app` 必须走同一条装配路线, 不能让 `run()` 成为
唯一正确入口.

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

默认建议:

- `install_signal_handlers=None` 时取 `cli_mode` 的值;
- CLI 模式默认接管 `SIGINT` 和 `SIGTERM`;
- 嵌入模式默认不修改宿主 signal handler;
- `health_reporter=None` 时不创建健康报告 task;
- `duration=None` 时持续运行;
- `health_interval=1.0`.

嵌入已有 asyncio 应用时, 推荐 `await app.start()` / `await app.close()` 或
`async with app`, 而不是在已有 event loop 中调用基于 `asyncio.run()` 的 `app.run()`.

## 7. CLI 启动路线

CLI 只负责参数, 进程状态和配置路径. 应用基础设施由 `BotApp` 负责:

```text
butterbot run
  -> 解析 CLI 参数, 不导入 plugin
  -> RuntimeConfig.from_yaml(resolved_config_path)
  -> 导入用户应用工厂
  -> application(config=config, cli_mode=True)
  -> BotApp 内部完成阶段 B
       -> plugin_enabled=false: 不导入 plugin
       -> plugin_enabled=true: 动态导入并装配 plugin
  -> 登记 CLI RuntimeState
  -> app.run(health_reporter=...)
  -> finally 标记停止
```

CLI 应用入口统一为同步工厂或 `BotApp` 类:

```python
from butterbot.app import BotApp, RuntimeConfig


def app(*, config: RuntimeConfig, cli_mode: bool = True) -> BotApp:
    return BotApp(config=config, cli_mode=cli_mode)
```

CLI 不再向工厂注入 `SourceFactoryRegistry`. 已构造的对象入口 `app = BotApp()` 应在
本次 clean break 中删除, 因为它在 CLI 选择配置路径前已经完成配置加载, 无法满足
"CLI 先构造 RuntimeConfig, 再注入应用"的唯一顺序.

后台启动只改变进程边界. 子进程仍执行同一条前台装配路线.

## 8. 直接运行与嵌入路线

### 8.1 由开发者准备配置

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

### 8.2 由框架读取 YAML

```python
from butterbot.app import BotApp

app = BotApp(
    config_path="deploy/config.production.yaml",
    cli_mode=False,
)
app.run()
```

### 8.3 嵌入现有 event loop

```python
app = BotApp(
    config=config,
    cli_mode=False,
    logging_mode="external",
)

async with app:
    await host_shutdown_event.wait()
```

三种用法都通过同一个阶段 B 完成 Source 和可选插件装配. `cli_mode=False` 不会关闭
YAML 插件功能; 是否启用插件仍只看 `config.plugin_enabled`.

## 9. `plugins.enabled=false` 的精确行为

关闭插件时:

- 不导入 `butterbot.plugin`;
- 不索引 distribution entry point;
- 不扫描 `plugin_path`;
- 不解析插件 descriptor 或依赖;
- 不创建 `PluginManager`;
- 不调用插件 register/start/stop/aclose;
- `app.plugin_enabled is False`;
- 应用健康中的插件列表为空;
- 内置和用户手工添加的 Source 正常注册, 启动和关闭;
- Source, EventBus, API 和日志仍遵守完整生命周期.

配置中的 `plugin_list`, `plugin_path`, `config` 和 `lifecycle` 可以保留, 便于用户先
编辑插件设置再开启总开关. 阶段 A 只校验 `plugins` 是 mapping 且 `enabled` 是 bool.
插件专属字段在开关为真或执行显式插件管理命令时再做完整校验.

## 10. `plugins.enabled=true` 的精确行为

启用插件时:

1. app assembler 动态导入插件运行时;
2. 完整校验插件设置;
3. 索引 entry point 和本地 manifest;
4. 只导入 `plugin_list` 选中的插件;
5. 校验 core 版本, distribution 依赖, plugin ID, 依赖图和 capability;
6. 按拓扑顺序执行 `@configure`;
7. 解析最终 Source 配置并自动注册 Source;
8. Source 启动前注册 Handler;
9. Source 全部 ready 后按依赖顺序执行 `on_start`;
10. 关闭时按逆依赖执行 `on_stop` 和资源清理, 再关闭其余 Source, EventBus 和 API.

任何插件准备错误都应使应用构造失败并逆序回滚已经登记的 builder, factory 和 Source.
不能自动退回无插件模式继续运行.

## 11. 基础设施状态与幂等性

建议给 `BotApp` 增加私有装配状态:

```text
NEW -> PREPARING -> PREPARED -> RUNNING -> CLOSING -> CLOSED
                    |
                    +-> PREPARE_FAILED
```

要求:

- Source 自动注册只执行一次;
- `start()`, `run()` 和 `__aenter__()` 共用 `_ensure_prepared()`;
- 构造期直接完成准备时, `_ensure_prepared()` 是 no-op;
- 准备失败必须撤销插件注册, 已创建 Source, 日志 lease 和内部 registry;
- `PREPARE_FAILED` 实例不能被再次启动, 除非专门设计可证明安全的重试协议;
- `close()` 对尚未启动但已经准备的应用仍要完整释放资源;
- `plugins.enabled=false` 分支不能为了统一代码而创建空 manager.

## 12. 迁移步骤

建议按以下顺序实施, 每一步独立提交:

1. 将 `SourceRef` 移入 core, 清除 app 对 plugin 的导入;
2. 将插件设置的最小总开关解析移入 app 配置层;
3. 把 `RuntimeConfig` 拆成结构化解析和内部准备两个阶段;
4. 新增 app 内部 runtime assembler, 隐藏 `SourceFactoryRegistry`;
5. 让 `BotApp` 根据配置动态导入插件运行时;
6. 修改 CLI 为"先 RuntimeConfig, 后应用工厂";
7. 删除 CLI 工厂的 `source_factory_registry` 参数和已构造对象入口;
8. 延迟导入 CLI 插件子命令及插件异常;
9. 增加 `plugin_enabled`, `cli_mode` 和执行阶段参数;
10. 更新 examples, API 文档, 稳定性 snapshot 和外部插件 fixtures.

## 13. 验收标准

### 13.1 零导入

在全新 Python 子进程中分别执行 CLI 和直接运行的禁用插件配置, 使用 import guard
在任何 `butterbot.plugin` 导入时立即失败. 两条路线都必须完成 Source 启动和关闭.

同时断言:

```python
assert not any(
    name == "butterbot.plugin" or name.startswith("butterbot.plugin.")
    for name in sys.modules
)
assert app.plugin_enabled is False
assert app._optional_runtime is None
```

### 13.2 路线一致

同一份 RuntimeConfig 通过 CLI 工厂和直接 `BotApp` 构造后, 应得到相同的:

- 已准备配置;
- Source catalog;
- Source 启动与关闭顺序;
- 插件启用判断;
- 缺少 adapter extra 时的错误;
- 失败回滚结果.

### 13.3 启用插件

现有三个外部插件 wheel fixture 和本地目录插件 fixture 继续覆盖:

- builder/factory 配置阶段;
- Handler 注册;
- Source 所有权;
- 依赖顺序;
- 注册失败回滚;
- Source 启动失败回滚;
- 幂等关闭.

### 13.4 嵌入模式

覆盖:

- `cli_mode=False` 不安装 signal handler;
- `logging_mode="external"` 不修改宿主 logger;
- 用户注入 RuntimeConfig;
- 框架按 `config_path` 加载 RuntimeConfig;
- 已有 event loop 中使用异步上下文;
- 两个应用使用隔离 registry, 不共享插件或配置准备状态.

## 14. 最终判断

该方案可行, 并且比继续维护 `PluginBootstrap -> application factory -> BotApp` 与
`BotApp.run()` 两套装配路线更清晰. 关键不是增加 `cli_mode` 分支, 而是建立唯一顺序:

```text
配置结构化完成
  -> 根据配置决定是否导入插件
  -> 汇总 builder/factory
  -> 准备最终配置
  -> 自动注册 Source
  -> 启动生命周期
```

`cli_mode` 只表达宿主和执行权限, `plugin_enabled` 只表达配置决策. 两者正交后,
普通 CLI 用户不需要理解内部 registry, 高级开发者仍能控制配置, 日志, 信号和 event
loop, 并且禁用插件可以得到可验证的零插件运行时成本.
