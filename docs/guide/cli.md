---
title: 命令行
---

# 命令行

## 初始化

在空目录中执行：

```bash
butterbot init
```

命令一次性创建可启动环境：

```text
config.yaml
app.py
plugins/
└── example.hello/
    ├── plugin.toml
    └── plugin.py
```

示例插件已经写入 `plugins.plugin_list`。初始化不会覆盖任何同名目标；目标存在时会
直接报错。

## 运行入口与配置文件

最短启动命令是：

```bash
butterbot run
```

默认约定如下：

- 应用入口：`app.app`；
- YAML：当前工作目录的 `config.yaml`。

位置参数继续可用：

```bash
butterbot run mybot.application.app
```

`-path` 显式覆盖应用入口，`-config` 显式覆盖 YAML：

```bash
butterbot run \
  -path mybot.application.app \
  -config ./deploy/config.production.yaml
```

同时提供位置参数和 `-path` 时，以 `-path` 为准。相对 `-config` 以执行命令时的
工作目录解析；相对 `plugins.plugin_path` 则以该 YAML 所在目录解析。`--path` 和
`--config` 也是等价写法。

`app.py` 使用具名同步工厂. 无论是否显式指定 `-config`, 官方项目都只采用这一种
入口. CLI 会把解析好的 `RuntimeConfig` 和当前 Source 注册表作为关键字参数传给
工厂.

`butterbot init` 默认生成工厂入口：

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

工厂入口必须接受 `config` 和 `source_factory_registry` 两个关键字参数, 并返回
`BotApp`. 不要在模块导入时构造或运行 Bot, 运行与关闭生命周期由 CLI 持有.

::: danger 导入阶段不要启动应用
如果入口模块在顶层执行 `run()`, 模块导入会阻塞, CLI 无法登记后台状态, 也
无法可靠执行 `status`、`restart` 和 `stop`.
:::

## 项目配置界面

```bash
butterbot config
butterbot config -config ./deploy/config.production.yaml
```

这是基于 Click 的全副屏交互终端。目前可以切换插件系统总开关；`Sources` 单独
占位，等待后续接入 Source 自动发现和配置。使用方向键或 `j/k` 移动，在总开关上
按空格或 Enter 切换，按 `q` 保存，按 Esc 取消。保存时会把完整结果原子写回 YAML，
未操作的插件列表、插件私有配置、Source 和其他字段保持不变。

## 插件配置界面

```bash
butterbot plugin
butterbot plugin -config ./deploy/config.production.yaml
```

界面使用备用屏幕整屏重绘，退出后恢复原终端内容。它会列出当前环境和
`plugins.plugin_path` 中发现的全部插件，并显示每个插件的 distribution 或目录
来源位置。

插件系统总开关、候选选择、检索目录和生命周期参数分开配置：

- 方向键或 `j/k`：移动光标；
- 空格或 Enter：切换总开关或当前插件；
- 在检索目录上按 Enter：修改 `plugins.plugin_path`；
- 在生命周期栏按 Enter：修改 start、stop、cleanup、drain 超时；
- `q` 或 `s`：保存全部修改；
- Esc：取消且不写文件。

stdin/stdout 不是真实终端时，例如 CI 或管道环境，界面自动降级为 Click 的编号与
确认提示，不输出 ANSI 控制序列。

关闭总开关不会清空已经选择的插件；因此可以先完成插件列表配置，再决定是否让
`butterbot run` 启动插件系统。YAML 的 `plugins.enabled` 是运行时唯一总开关，
manifest 不包含启用状态。

## 插件查看与模拟导入

静态列出全部候选：

```bash
butterbot plugin list
butterbot plugin list -config ./deploy/config.production.yaml
```

`list` 显示 ID、名称、版本、来源、是否在 `plugin_list`、插件系统总开关和发现位置。
它只索引 distribution 元数据和本地 manifest，不导入插件代码。

模拟导入：

```bash
butterbot plugin check
butterbot plugin check -config ./deploy/config.production.yaml
```

`check` 不接受应用入口或插件名。它按 YAML 报告：

- `LOADED`：已被总开关和 `plugin_list` 选中，并成功导入；
- `BLOCKED`：被总开关或 `plugin_list` 拦截，没有导入；
- `MISSING`：YAML 选择了未发现的名称；
- `FAILED`：选中插件导入或身份校验失败。

存在 `MISSING` 或 `FAILED` 时退出码为 `1`，其余情况为 `0`。旧的顶层 `check` 和
复数 `plugins` 命令不再提供。

## 前台与后台运行

前台运行：

```bash
butterbot run
```

前台模式适合终端、容器和 systemd。`SIGINT`、`SIGTERM` 都进入 `BotApp.close()`
路径。

后台运行：

```bash
butterbot run --background
```

stdout 和 stderr 追加到 `.butterbot/butterbot.log`。状态写入
`.butterbot/runtime.json`，其中记录 PID、应用入口、配置路径、工作目录和时间等
运行元数据，不保存配置内容、环境变量或 Secret。

后台命令返回成功表示应用入口已经导入且子进程已登记。刚登记时
`status` 显示 `starting`；进程会定期写入聚合的 Source/插件健康摘要，全部
就绪后显示 `ready`。摘要不保存配置、Secret 或异常消息。

## Debug

```bash
butterbot run --background --debug
```

`--debug` 让配置和入口加载错误保留完整 traceback。后台状态会记录该设置，
`restart` 沿用它。

## 状态与优雅停止

```bash
butterbot status
butterbot stop
```

`status` 会显示 Source ready 数和插件 healthy 数。`starting`、`ready` 或
`stopping` 时退出码为 `0`；`degraded` 或健康报告超过 5 秒未更新时为
`1`；没有记录或已经停止时为 `3`。一个工作目录只管理一个进程，管理命令应在
启动时的目录执行。

`stop` 发送 `SIGTERM`，等待 `BotApp.close()` 按插件、Source、EventBus、API 的
顺序释放资源。固定等待上限为 10 秒；超时只报告错误，不会强制终止一个已经进入
正常运行阶段的应用。

## 完整重启

```bash
butterbot restart
```

旧版本留下的暂停状态会在执行 `stop` 时先恢复，再进入同一优雅停止路径。

`restart` 不做热重载。它等待旧 PID 完全退出，再创建新解释器，并复用状态文件中
记录的应用入口、配置文件和 debug 设置。即使上次进程已经停止，只要运行状态仍在，
也可以重新启动。新进程继承执行 `restart` 时的当前环境。

当前没有 `reload` 命令，也不会在原进程内替换模块或配置。
