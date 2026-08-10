---
title: 插件开发
---

# 插件系统

ButterBot `3.1.0` 的插件 API 是稳定契约，用于可信代码、启动期加载的行为扩展。插件可以来自已安装
distribution 的 `butterbot.plugins` entry point，也可以来自项目的便携目录；两种
来源进入相同的身份、依赖、Handler 注册和生命周期控制面。

已文档化且从公共门面导出的作者 API 在 `3.x` 内遵守 SemVer。experimental 能力必须
明确标注；未导出的运行时控制面属于 internal API。

插件只扩展行为，不拥有 Source。应用配置和 `BotApp` 负责创建 Source，插件通过
`@register` 使用已经存在的事件能力。旧的 `@configure`、`ConfigRegistrar`、配置
builder、Source factory、Source adopt 路线已经删除。

::: danger 插件拥有当前 Python 进程的完整权限
插件可以访问文件、网络、环境变量和进程对象。生命周期 registrar 不是安全沙箱；
只安装并启用可信发布者的插件。
:::

## 启用和零导入边界

环境覆盖完成后的 `plugins.enabled` 是唯一总开关：

```yaml
plugins:
  enabled: true
  plugin_list: [HelloPlugin]
  plugin_path: ./plugins
  config:
    local.hello:
      greeting: hello
```

关闭时，CLI、`BotApp.run()`、`await app.start()` 和 `async with app` 都不会导入
`butterbot.plugin`、扫描候选或创建空 manager。开启时只加载 `plugin_list` 选中的
名称；目录存在或 distribution 已安装都不会自动授权执行。

插件加载失败不会降级为无插件运行。缺失候选、重复身份、版本不兼容、依赖错误或
私有配置校验失败都会使应用准备失败。

## Distribution entry point

打包插件通过固定 entry point group 暴露实例、零参数类或同步 factory：

```toml
[project]
name = "butterbot-plugin-example"
version = "1.0.0"
dependencies = ["butterbot-python>=3.1,<4"]

[project.entry-points."butterbot.plugins"]
"ExampleHandlerPlugin" = "example_plugin:ExampleHandlerPlugin"
```

entry point 名是静态可读的 `plugin_name`，必须与实现类名完全相同。distribution
插件用 `PluginDescriptor` 声明稳定 ID、版本和依赖：

```python
from butterbot.plugin import ButterPlugin, PluginDescriptor


class ExampleHandlerPlugin(ButterPlugin):
    descriptor = PluginDescriptor(
        plugin_id="example.handler",
        version="1.0.0",
        requires_core=">=3.1,<4",
        requires_plugins=(),
    )
```

## 便携本地目录

本地插件不需要单独打包：

```text
project/
├── config.yaml
├── app.py
└── plugins/
    └── local.hello/
        ├── plugin.toml
        ├── plugin.py
        └── assets/
```

`plugin.toml` 是 descriptor 的唯一来源：

```toml
schema_version = 2
plugin_name = "HelloPlugin"
version = "0.1.0"
requires_core = ">=3.1,<4"
entry = "plugin.py"
requires_plugins = []
requires_distributions = []
```

目录名就是稳定 `plugin_id`，上例为 `local.hello`。入口模块必须且只能定义一个
具体 `ButterPlugin` 子类，类名必须等于 `plugin_name`。loader 使用隔离的合成
package namespace，不修改 `sys.path`；绝对入口、嵌套入口、目录逃逸和符号链接都会
在 import 前被拒绝。

未启用候选只读取 entry point 元数据、本地 manifest 和 fingerprint 所需字节，不
执行 Python 顶层代码。`requires_distributions` 只检查当前环境，不调用 pip 或 uv。

## Handler 与应用 Source

插件使用 `@register(source_kind, status)` 声明逻辑订阅：

```python
from butterbot.core import Event
from butterbot.plugin import ButterPlugin, register


class HelloPlugin(ButterPlugin):
    @register("example.events", "example.ready")
    async def handle_ready(self, event: Event) -> None:
        print(event.data)
```

应用必须先拥有匹配的 Source：

```python
from butterbot.app import BotApp, RuntimeConfig
from myapp.sources import ExampleSource


def app(*, config: RuntimeConfig, cli_mode: bool = True) -> BotApp:
    application = BotApp(config=config, cli_mode=cli_mode)
    application.add_source(ExampleSource, config_key="primary")
    return application
```

Handler 注册发生在 Source 启动前。没有匹配时准备启动失败；匹配多个实例时需要在
`plugins.config.<plugin-id>.config_key` 指定实例，或在 `@register` 上显式设置
`allow_multiple=True`。

插件可以通过窄化上下文查询已有能力：

```python
source = self.context.get_source("example.events")
api = self.context.get_api(ExampleApi)
```

上下文不提供 Source 创建、接管、配置写回或其他插件实例访问能力。

## 私有配置

`settings` 是当前插件隔离的只读 mapping。需要强校验时声明 `PluginConfig`：

```python
from butterbot.plugin import ButterPlugin, PluginConfig


class HelloConfig(PluginConfig):
    config_key: str | None = None
    greeting: str = "hello"


class HelloPlugin(ButterPlugin[HelloConfig]):
    config_model = HelloConfig
```

类型化配置在应用准备期间、Source 启动前校验。未知字段默认拒绝，模型不可修改。
本地插件可通过 `resource_root` 读取自身资源；distribution 插件该值为 `None`。

## 生命周期与资源

插件只需按需覆盖异步 `on_start()` 和 `on_stop()`：

```python
class HelloPlugin(ButterPlugin):
    async def on_start(self) -> None:
        self.context.spawn(self.consume(), name="hello.consume")
        self.context.add_cleanup(self.close_client)

    async def on_stop(self) -> None:
        await self.flush()
```

固定顺序是：

```text
最终 RuntimeConfig
-> 应用 Source 装配
-> 配置允许时索引并加载选中插件
-> 校验插件配置和依赖
-> 注册 Handler
-> 启动全部 Source
-> on_start（依赖顺序）
-> 运行
-> on_stop（逆依赖顺序）
-> 撤销 Handler 并清理插件资源
-> 关闭 Source、EventBus 和 API
```

Source 启动失败、插件启动失败或取消都会回滚 Handler 和已进入生命周期的资源。
`context.spawn()` 创建的任务和 `context.add_cleanup()` 登记的回调由插件作用域持有，
关闭时会取消、等待并逆序清理。

`plugins.lifecycle` 分别控制 start、stop、cleanup 和 Handler drain 超时。诊断状态只
记录稳定 ID、阶段和异常类型，不记录异常消息、Secret 或完整私有配置。

## 管理命令

```bash
butterbot plugin list
butterbot plugin check
butterbot plugin config
```

`list` 只读取元数据；`check` 仅在总开关开启时导入已选择代码，并在短生命周期子
进程中完成校验；`config` 是唯一插件管理写操作，只原子更新指定 YAML。三者都不
构造 `BotApp`、`PluginManager`、Source、网络连接或后台任务。

## 发布前验证

插件至少应验证：

- 关闭总开关时顶层代码不会执行；
- clean venv 能发现 distribution entry point；
- 本地目录在仓库外工作目录中仍能加载；
- Handler 只依赖稳定的 `source_kind`，不导入具体 Source 实现；
- 注册、Source 启动和 `on_start` 失败均无残留 Handler 或任务；
- 重复关闭幂等；
- 日志和诊断不包含私有配置或 Secret。
