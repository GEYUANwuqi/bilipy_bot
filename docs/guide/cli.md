---
title: 命令行
---

# 命令行

::: danger 使用 CLI 时不要在模块顶层调用 `app.run()`
`butterbot run mybot.app:app` 需要先导入模块并取得 `app`。如果模块导入过程中直接
执行 `app.run()`，导入会阻塞，CLI 无法登记后台状态，也无法可靠提供
`status`、`restart` 和 `close`。
:::

## 应用对象与 factory

在用户模块中定义已经注册好 Source 和 Handler 的 `BotApp` 对象：

```python
# mybot/app.py
from butterbot.app import BotApp
from butterbot.sources.napcat import NapcatSource

app = BotApp()  # 导入模块时读取运行目录的 config.yaml
source = app.get_source(NapcatSource, "qq_account")
assert source is not None
```

CLI 使用 `module:attribute` 找到这个对象。未启用插件时，入口可以是 `BotApp`
实例或返回 `BotApp` 的零参数同步 factory；不支持 coroutine。单 Bot 项目建议让
CLI 统一拥有运行和关闭生命周期，因此文件末尾不需要写 `app.run()`：

```bash
butterbot run mybot.app:app --background
```

启用实验插件时，入口必须是接受 `config` 和 `source_factory_registry` 关键字参数
的同步 factory。bootstrap 需要先注册插件 builder/factory，再构造应用：

```python
from butterbot.app import BotApp


def create_app(*, config, source_factory_registry):
    return BotApp(
        config=config,
        source_factory_registry=source_factory_registry,
    )
```

```bash
butterbot check mybot.app:create_app
butterbot run mybot.app:create_app
```

已构造的全局 `BotApp` 不能用于插件模式。完整边界见
[实验性插件系统](/extensions/plugins.html)。

## 插件命令

列出当前 `config.yaml` 能发现的 distribution 和本地目录候选：

```bash
butterbot plugins list
```

输出包含 ID、版本、来源类型、是否已选择、核心兼容、依赖结果和来源位置。未选择的
本地候选只读取 `plugin.toml` 和 fingerprint 输入，不执行代码；distribution
候选未选择时不会为了显示版本而导入，版本、兼容和依赖会标记为延迟检查。

使用与运行期相同的发现、导入、两阶段注册和回滚路径检查插件：

```bash
butterbot plugins check
butterbot plugins check mybot.app:create_app
```

创建可直接复制的本地目录插件模板：

```bash
butterbot plugins init local.hello
```

模板位于 `./plugins/local.hello/`，只有 `plugin.toml` 和 `plugin.py`，不创建
`pyproject.toml`、不安装依赖、不修改 `config.yaml`，也不会覆盖已有目录。生成的
entry 模块只定义一个 `ButterPlugin` 子类，由 loader 自动实例化，无需 factory。

## 入口选择

### 单 Bot 项目

推荐只定义 `app`，由 CLI 启动：

```python
# app.py
from butterbot.app import BotApp

app = BotApp()
# 在这里添加 Source 和 Handler，但不要在模块顶层调用 app.run()
```

```bash
uv run butterbot run app:app --background
```

### 同时支持 CLI 和直接执行

需要同时支持 `butterbot run app:app` 和 `uv run app.py` 时，必须使用主模块保护：

```python
from butterbot.app import BotApp

app = BotApp()


if __name__ == "__main__":
    app.run()
```

CLI 导入 `app.py` 时 `__name__` 不是 `"__main__"`，不会重复进入 `app.run()`；
直接执行文件时才由该文件拥有生命周期。

### 嵌入其他系统

如果调用方是同步顶层入口，并且当前线程没有正在运行的事件循环，可以调用
`app.run()`。如果嵌入 ASGI、Jupyter 或其他已经拥有 asyncio 事件循环的系统，
不要调用 `app.run()`；应使用：

```python
async with app:
    await run_host_application()
```

也可以显式调用 `await app.start()`，并在 `finally` 中执行
`await app.close()`。详见[生命周期](./lifecycle.md)。

## 检查配置

在应用运行目录执行：

```bash
butterbot check
# 插件模式建议提供与 run 相同的 factory
butterbot check mybot.app:create_app
```

该命令固定检查当前目录的 `config.yaml`，验证 YAML 结构、环境变量引用、
`source_name`、`kwarg` 结构和 builder 构建。它会静态扫描本地 manifest，并对
已选择候选执行插件 discovery、两阶段配置、Source 构造和插件运行阶段注册，但
不会启动外部 Source；结束前会完整撤销测试注册。提供 entry point 时会导入该应用
factory，从而与 `run` 使用同一构造路径。配置有效时退出码为 `0`，无效时为 `1`。

检查会读取当前进程环境，因此生产部署中需要同时注入配置引用的变量。

## 运行

前台运行：

```bash
butterbot run mybot.app:app
```

前台模式适合终端、容器和 systemd。未启用插件时，应用模块中的 `BotApp()` 从
执行命令的当前目录读取 `config.yaml`；插件模式由 bootstrap 读取一次配置并注入
应用 factory。`SIGINT`、`SIGTERM` 都进入 `BotApp.close()` 路径。

后台运行：

```bash
butterbot run mybot.app:app --background
```

后台模式把 stdout 和 stderr 追加到 `.butterbot/butterbot.log`。状态固定写入
`.butterbot/runtime.json`，其中只有 PID、应用入口、工作目录和时间等运行元数据，
不保存配置内容或环境变量。

后台命令返回成功表示应用对象已经导入、子进程已登记，不代表所有外部 Source 都
已通过远端健康检查。启动后的连接失败会写入日志，并由 `status` 反映进程是否仍然
存活。

如果当前实例已被 `stop` 暂停，再次执行 `run` 不会创建新进程，而是恢复原 PID：

```bash
butterbot run mybot.app:app --background
```

CLI 会明确输出“已恢复原进程”和“未创建新实例”。此时命令中的入口和参数不会
替换暂停实例；需要全新进程应使用 `restart`，或先 `close` 再 `run`。

## Debug

```bash
butterbot run mybot.app:app --background --debug
```

`--debug` 让 CLI 配置和入口加载错误保留完整 traceback，并记录在运行状态中，
`restart` 会沿用该设置。该参数暂不改变 `BotApp` 构造参数，后续可以在保持命令行
兼容的前提下用于传递调试配置。

## 状态

```bash
butterbot status
```

正在运行时退出码为 `0`；没有记录或已经停止时退出码为 `3`。Linux 上状态文件会
记录 `/proc` 进程启动标识，降低 PID 被复用后误操作其他进程的风险。

一个运行目录只管理一个进程。所有命令必须在启动应用时的目录执行。

## 暂停与恢复

```bash
butterbot stop
```

`stop` 使用操作系统 `SIGSTOP` 暂停整个进程，保留 PID、内存和当前运行状态。
再次执行原来的 `run module:app` 命令会发送 `SIGCONT`，恢复同一个进程：

```text
run -> PID 100
stop -> PID 100 暂停
run -> PID 100 恢复，不创建新实例
```

::: warning 暂停不会释放资源
CLI `stop` 不等同于 Python API 的 `await app.stop()`。暂停期间事件循环、Handler
和心跳全部冻结，现有 socket 也不会主动关闭；长时间暂停可能导致远端连接或请求
超时。需要释放 Source、EventBus 和 API 资源时应使用 `close`。
:::

`stop` 和恢复依赖 `SIGSTOP/SIGCONT`。不支持这两个信号的平台会明确报错。
对已经暂停的实例再次执行 `stop` 是幂等操作。

## 关闭

```bash
butterbot close
```

`close` 发送 `SIGTERM` 并等待旧进程完全退出。若实例处于暂停状态，会先发送
`SIGCONT`，再进入 `BotApp.close()` 的优雅关闭路径。固定等待上限为 10 秒；超时
只报告错误，不发送 `SIGKILL`，以免绕开 Source、EventBus 和 API 的清理顺序。

## 完整重启

```bash
butterbot restart
```

`restart` 不执行热重载，顺序固定：

1. 若旧进程暂停，先发送 `SIGCONT`；
2. 向旧进程发送 `SIGTERM`；
3. 等待旧 PID 完全退出；
4. 启动新的 Python 解释器和新 PID；
5. 重新导入应用模块；
6. 应用模块中的 `BotApp()` 重新读取运行目录的 `config.yaml`；
7. 完整执行 Source、EventBus 和 API 的启动生命周期。

即使上次进程已经停止，只要 `.butterbot/runtime.json` 仍在，也可以重新启动。

状态文件不会保存环境变量或 Secret。新进程继承执行 `restart` 命令时的当前环境，
因此服务管理器必须在每次调用时提供相同的环境配置。

当前没有 `reload` 命令，也不会在原进程中重新加载模块或替换配置。
