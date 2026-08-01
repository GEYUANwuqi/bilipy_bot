---
title: 实验性插件系统
---

# 实验性插件系统

ButterBot 3.x 提供可信代码、启动期加载的实验性混合插件系统。插件可以来自已安装
distribution 的 `butterbot.plugins` entry point，也可以是项目 `./plugins`
下无需 `pyproject.toml`、wheel 或安装步骤的便携目录。两种来源进入同一套身份、
依赖、注册、回滚和关闭控制面。

API 位于 `butterbot.plugin`；它仍可能在 3.x 开发版本中
发生破坏性调整。

`butterbot.plugin` 只导出插件契约；`Event`、Filter、`BaseType`、`BaseSource`
等 core 类型由插件作者按需从 `butterbot.core` 导入。

::: danger 插件拥有当前 Python 进程的完整权限
插件可以访问文件、网络、环境变量和进程内对象。registrar 是生命周期和所有权边界，
不是安全沙箱。只安装并启用可信发布者的插件。
:::

当前不支持运行期安装、单插件卸载、热重载、依赖自动安装、签名验证或插件市场。
插件随应用进程一起加载和关闭。

## 来源、发现与授权

`plugins.enabled` 是插件系统总开关。开启后，框架会索引已配置来源，但只导入和
注册 `plugins.plugin_list` 明确选择的代码。manifest 不参与启用决策，自动发现
不等于默认执行。

`plugins.plugin_list` 使用唯一的 `plugin_name`。同名候选会在导入前直接报错；两个已
选择候选若返回相同 `plugin_id`，也会在注册前失败。不存在“本地覆盖已安装版本”
的隐式优先级。

### Distribution entry point

打包插件是独立 Python distribution，并通过固定 entry point group
`butterbot.plugins` 暴露一个插件实例、零参数类或 factory：

```toml
[project]
name = "butterbot-plugin-example"
version = "1.0.0"
dependencies = ["butterbot-python>=3.1.0.dev2,<4"]

[project.entry-points."butterbot.plugins"]
"ExampleFeedPlugin" = "example_plugin:ExampleFeedPlugin"
```

entry point 名是无需导入代码即可读取的 `plugin_name`，必须和
实际插件类名完全一致。`plugin_id` 是依赖和私有配置使用的稳定小写标识。启动加载
时框架会再次比较 entry point 名和 `type(instance).__name__`，不一致会在注册前失败。

```python
from butterbot.plugin import ButterPlugin, PluginDescriptor


class ExampleFeedPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.feed",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=(),
        provides=("example.events",),
    )
```

### 便携本地目录

本地插件使用固定布局：

```text
project/
├── config.yaml
├── app.py
└── plugins/
    └── local.hello/
        ├── plugin.toml
        ├── plugin.py
        ├── helpers.py
        └── assets/
            └── greeting.txt
```

`plugin.toml` 是本地插件 descriptor 的唯一事实来源：

```toml
schema_version = 2
plugin_name = "HelloPlugin"
version = "0.1.0"
requires_core = ">=3.1.0.dev2,<4"
entry = "plugin.py"
requires_plugins = []
requires_distributions = []
```

本地插件 ID 直接取插件目录名，因此 `plugins/local.hello/` 的稳定 ID 是
`local.hello`；`plugins.plugin_list` 使用 `HelloPlugin`，`requires_plugins` 和
`plugins.config` 使用 `local.hello`。目录名必须符合 plugin ID 的小写稳定标识
规则。`plugin_name` 必须是合法 Python 类名、与入口模块中的实现类完全一致，并在
所有候选中保持唯一。

入口只允许插件根目录的直接 `.py` 子文件。该模块必须且只能定义一个
`ButterPlugin` 子类，loader 会自动实例化；插件代码不重复声明 descriptor，也不需要
factory：

```python
from butterbot.core import Event
from butterbot.plugin import ButterPlugin, register


class HelloPlugin(ButterPlugin):
    @register("example.events", "example.ready")
    async def handle_ready(self, event: Event) -> None:
        greeting = str(self.settings.get("greeting", "hello"))
        resource = self.resource_root
```

只有 `candidate.__module__ == entry_module.__name__` 的具体 `ButterPlugin` 子类会被
计入，因此从 helper 导入的基类或其他插件类不会被误选。找到零个或多个候选都会
报错；实现不会扫描“第一个看起来像插件的类”，也不使用跨模块全局注册表。

同目录 helper 可使用 `from .helpers import ...`。loader 为每个来源建立合成 package
namespace，不修改 `sys.path`；符号链接、绝对入口、`..`、嵌套入口和目录逃逸会在
import 前被拒绝。未启用本地插件只读取 manifest 和用于 fingerprint 的入口字节，
不执行 Python 顶层代码。

`requires_distributions` 使用标准 Python distribution requirement，只在 import 前
检查当前环境，不会调用 pip/uv，也不会修改 lockfile。

两种来源在启动前统一检查重复 ID、核心版本、必需插件和依赖循环，并按确定的拓扑
顺序注册。目录插件可以依赖 distribution 插件，反向依赖也使用同一个 plugin ID
图。目录 manifest 不再声明 `provides`；实际 Source 能力和冲突由 owner-aware
注册结果校验，避免清单声明与代码行为漂移。distribution descriptor 暂时仍可声明
静态 capability。

当前仅支持 manifest `schema_version = 2`，未知字段和未知 schema 都会被拒绝，
避免拼写错误被静默忽略。experimental 阶段若需要不兼容 schema，会增加新的整数
版本；当前不包含 schema 1 兼容解析分支。

## 两阶段注册

配置阶段使用同步 `@configure` 方法，只登记 builder 和 Source factory，不能创建
任务或连接：

```python
from butterbot.plugin import ConfigRegistrar, configure


class ExamplePlugin(ButterPlugin):
    # descriptor 同上

    @configure
    def configure_source(self, registrar: ConfigRegistrar) -> None:
        registrar.register_builder("example", dict)
        registrar.register_factory(
            "example",
            FeedSource,
            factory_id="source",
        )
```

`factory_id="source"` 是 YAML 协议。它不依赖 `FeedSource` 的 Python 类名，因此类
重命名不会破坏用户配置。

Handler 直接使用 `@register(source_kind, status)` 声明订阅，不需要编写运行阶段
hook，也不需要导入 provider 的 Source 类：

```python
from butterbot.core import Event
from butterbot.plugin import (
    ButterPlugin,
    PluginDescriptor,
    register,
)


class HandlerPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.handler",
        version="1.0.0",
        requires_core=">=3.1.0.dev2,<4",
        requires_plugins=("example.feed",),
        provides=("example.handler",),
    )

    @register("example.events", "example.item")
    async def handle_item(self, event: Event) -> None:
        ...
```

基类从可选的 `plugins.config.<plugin-id>.config_key` 构造 `SourceRef`，再自动用
绑定 Handler 创建 `SubscriptionSpec`。没有配置键时只按 `source_kind` 匹配，唯一
结果会直接使用；同类 Source 有多个实例时才需要显式设置 `config_key`。插件不能
代替其他插件登记 Source 或 Handler。

插件按需覆盖固定生命周期回调，不需要装饰器：

```python
class HandlerPlugin(ButterPlugin):
    async def on_start(self) -> None:
        ...

    async def on_stop(self) -> None:
        ...
```

`on_start()` 在全部 Source 启动后按依赖顺序执行，`on_stop()` 在 Source 停止前按
依赖逆序执行。长期连接通常仍应由 Source 的生命周期管理，Handler task 由
EventBus 管理。

插件自己创建的短期后台任务和客户端资源交给运行上下文托管：

```python
async def on_start(self) -> None:
    self.context.spawn(self.worker(), name="example.worker")
    self.context.add_cleanup(self.client.aclose)
```

停止时框架先执行 `on_stop()`，再取消并等待托管任务，最后逆序执行清理回调。启动
到一半失败也会执行这条清理链。

## 配置与应用入口

只启用明确需要的插件，并显式配置本地来源：

```yaml
plugins:
  enabled: true
  plugin_list:
    - HelloPlugin
    - ExampleFeedPlugin
    - ExampleHandlerPlugin
  plugin_path: "./plugins"

  config:
    local.hello:
      greeting: "${HELLO_GREETING:-hello}"

  lifecycle:
    start_timeout: 30
    stop_timeout: 10
    cleanup_timeout: 10
    drain_timeout: 5

sources:
  primary:
    source_name: example
    kwarg:
      source: {}
```

相对 `plugins.plugin_path` 以 `config.yaml` 所在目录为基准，而不是调用方临时
cwd。`plugin_list` 是唯一插件白名单；没有写或显式写成空列表时都不会加载插件。
总开关为 `false` 时也不会扫描或执行插件。

`plugins.config.<plugin-id>` 只会作为不可变 mapping 注入该插件的
`ButterPlugin.settings` 和配置 registrar。插件不能看到其他插件 namespace；状态、
收据和默认错误不会保存配置值。本地插件的 `resource_root` 是 `plugin.toml`
所在目录，distribution 插件为 `None` 并应使用 `importlib.resources`。

插件可以把 `PluginConfig` 子类赋给 `config_model`，让私有配置在应用构造前完成
类型、必填字段和未知字段校验，再通过 `self.config` 读取不可变模型。未声明 schema
时保留 `settings` mapping 行为。

`plugins` 是 bootstrap 保留段，不会进入 `RuntimeConfig.get_config()`。可以使用
`BUTTERBOT__PLUGINS__PLUGIN_LIST='[HelloPlugin, ExampleHandlerPlugin]'` 覆盖插件列表。

CLI 官方入口只使用 `butterbot init` 生成的具名同步工厂. bootstrap 在构造应用前
注入配置和当前 Source registry:

```python
from butterbot.app import BotApp, RuntimeConfig, SourceFactoryRegistry


def app(
    *,
    config: RuntimeConfig,
    source_factory_registry: SourceFactoryRegistry,
) -> BotApp:
    return BotApp(
        config=config,
        source_factory_registry=source_factory_registry,
    )
```

查看候选、模拟导入并运行：

```bash
butterbot plugin list
butterbot plugin check
butterbot run
```

`plugin list` 只读取候选元数据；`plugin check` 按 YAML 模拟导入，并分别报告成功
加载和被配置拦截的插件。真正的配置解析、应用构造和运行阶段注册由 `run` 完成。

不要在模块导入时先构造全局 `BotApp` 对象；那会早于插件 builder 和 Source
factory 注册。CLI 始终走同一个 bootstrap，只有 `plugins.enabled: true` 才会导入
和注册 `plugin_list` 中的插件. bootstrap/manager 是框架 internal 控制面,
不从 `butterbot.plugin` 导出. 关闭总开关时可以继续保留插件选择、检索路径和
私有配置；`plugin list` 和交互配置仍会索引路径以展示候选。

创建包含示例插件的完整项目模板：

```bash
butterbot init
```

命令创建 `config.yaml`、`app.py` 和 `plugins/example.hello/`，不会安装依赖或覆盖
已有目标。之后可用裸 `butterbot plugin` 交互选择插件并写回 YAML。

## 生命周期、回滚与诊断

顺序固定为：

```text
静态索引 distribution entry point 和本地 manifest
-> 检查来源冲突
-> 按 plugin_name 应用 plugin_list 白名单
-> 只导入已选择候选
-> descriptor/依赖校验
-> @configure（依赖顺序）
-> 解析 RuntimeConfig
-> 构造全部配置 Source
-> 解析 @register Handler 声明（依赖顺序）
-> 启动 Source
-> on_start（依赖顺序）
-> 运行
-> on_stop（逆依赖顺序）
-> 插件注册项逆依赖顺序关闭
-> SourceManager / EventBus / ApiRegistry 关闭
```

builder、factory、Source、Handler 和 close callback 都有 owner 与撤销收据。配置、
注册、Source 启动或插件 `on_start()` 出现普通异常或取消时，bootstrap 会先调用
已进入启动阶段插件的 `on_stop()`，再逆序撤销本轮副作用。停止回调发生取消也不会
跳过其余插件和 Source 的清理。`SourceRef` 缺失、重复或歧义在 Source 启动前
报告。

`plugins.lifecycle` 控制单个插件的 start、stop、资源清理和 Handler 排空超时。
超时或普通清理错误只影响对应插件，管理器仍会处理逆依赖序列中的其余插件。

`PluginBootstrap.manager.statuses` 返回不含配置值和 secret 的诊断快照，并带有
稳定 `plugin_id`、实现类 `plugin_name`、`origin_kind`、`origin` 和本地 SHA-256
`fingerprint`。状态包括
`validated`、`configuring`、`configured`、`registering`、`registered`、
`started`、`failed`、`blocked` 和 `closed`。注册异常还提供
`PluginRegistrationError.plugin_id`、`phase` 和 `cause`。

每个状态的 `failures` 是不含异常消息和配置值的结构化记录，字段包括阶段、异常
类型、是否超时和是否取消；`healthy` 表示是否没有记录。后台托管任务失败会登记为
`background`，但不会擅自停止整个应用。

## 发布前验证

distribution 插件至少应在独立 wheel 中验证：

- entry point 能从 clean venv 发现；
- Handler-only distribution 从 `butterbot.plugin` 导入插件契约，从
  `butterbot.core` 导入事件与过滤类型；
- provider/consumer 不通过实现类互相耦合；
- import、register 和 Source start 失败不留下注册项或 task；
- 重复关闭幂等。

核心仓库的 `scripts/smoke_plugins.py` 使用 Source-only、Handler-only 和 Combined
三个独立 distribution，在 Python 3.12、3.13 和 3.14 CI 上执行这一契约。

本地目录插件还应验证：

- 插件目录不含 `pyproject.toml`，只复制目录即可工作；
- 仓库外 cwd、不同绝对路径和未设置 `PYTHONPATH` 时行为一致；
- disabled 候选顶层代码不执行；
- Source-only、Handler-only、Combined 与混合来源依赖进入同一生命周期；
- 关闭后没有遗留 Source、Handler 或 asyncio task。

核心仓库的 `scripts/smoke_local_plugins.py` 会把四类本地 fixture 复制到两个随机
绝对路径，并在仅安装 ButterBot 与 provider wheel 的 Python 3.12、3.13、3.14
环境中验证这些条件。
