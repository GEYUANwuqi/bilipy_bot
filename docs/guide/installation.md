---
title: 安装
---

# 安装

## 本页目标

准备可运行 ButterBot 的 Python 环境，并验证公共门面可以导入。

## 运行环境

- Python：`>=3.12`，由 `pyproject.toml` 的 `requires-python` 约束。
- 项目开发包管理器：`uv`。
- 当前 CI 对 Python 3.12、3.13 和 3.14 运行测试；这描述的是仓库当前
  测试矩阵，不是对未来 Python 版本的保证。

## 安装已发布包

在自己的 uv 项目中添加依赖：

```bash
uv add butterbot-python
```

如果当前目录还不是 uv 项目，先运行 `uv init`。安装包名是
`butterbot-python`，Python 导入名是 `butterbot`。

基础安装只包含核心、CLI 和插件契约. 按实际 adapter 选择 extra:

```bash
uv add "butterbot-python[napcat]"     # NapCat, 显式安装 aiohttp
uv add "butterbot-python[bilibili]"  # Bilibili SDK 和 aiohttp
uv add "butterbot-python[all]"        # 全部内置 adapter
```

NapCat 和 Bilibili 都直接依赖 `aiohttp`; Bilibili extra 不依赖
上游 SDK 是否恰好传递安装它.

## 从仓库开发

```bash
git clone https://github.com/GEYUANwuqi/ButterBot.git
cd ButterBot
uv sync --locked --dev
```

`--locked` 要求安装结果与 `uv.lock` 一致; `--dev` 会安装测试、lint、
类型检查与全部内置 adapter 的开发依赖.

## 验证安装

```bash
uv run python -c "from butterbot.app import BotApp, RuntimeConfig; print(BotApp.__name__)"
```

预期输出：

```text
BotApp
```

也可以查看安装版本：

```bash
uv run butterbot --version
```

## 平台说明

框架入口使用 `asyncio.run()`。`BotApp.run()` 会在支持
`loop.add_signal_handler()` 的平台处理 `SIGINT` 和 `SIGTERM`；不支持该接口的
平台会回退到 `KeyboardInterrupt` 路径。不要依赖某个平台特有的事件循环策略。

## 常见安装问题

### `uv: command not found`

先按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)
安装 uv，再重新打开终端验证 `uv --version`。

### Python 版本不满足

使用 uv 安装并选择受支持版本：

```bash
uv python install 3.12
uv sync --locked --dev --python 3.12
```

### 导入名写错

安装名是 `butterbot-python`，导入路径是 `butterbot`。应用入口从
`butterbot.app` 导入，不要从 `butterbot.core` 导入 `BotApp`。

### 缺少 adapter extra

配置了 NapCat 或 Bilibili Source 但没有安装对应 extra 时, 构造会抛出
带完整安装命令的 `ConfigError`. 基础 wheel 仍可以导入 `butterbot.app`,
运行空 `BotApp` 和加载不依赖内置 adapter 的插件.

## 下一步

- [运行最小闭环示例](./quick-start.md)
- [使用命令行运行应用](./cli.md)
