---
title: 安装
---

# 安装

## 本页目标

准备可运行 bilipy_bot 的 Python 环境，并验证公共门面可以导入。

## 运行环境

- Python：`>=3.12`，由 `pyproject.toml` 的 `requires-python` 约束。
- 项目开发包管理器：`uv`。
- 当前 CI 对 Python 3.12、3.13 和 3.14 运行测试；这描述的是仓库当前
  测试矩阵，不是对未来 Python 版本的保证。

## 安装已发布包

在自己的 uv 项目中添加依赖：

```bash
uv add bilipy-bot
```

如果当前目录还不是 uv 项目，先运行 `uv init`。包名使用连字符
`bilipy-bot`，Python 导入名使用下划线 `bilipy_bot`。

## 从仓库开发

```bash
git clone https://github.com/GEYUANwuqi/bilipy_bot.git
cd bilipy_bot
uv sync --locked --dev
```

`--locked` 要求安装结果与 `uv.lock` 一致；`--dev` 会安装测试、lint 和类型检查
工具。仓库没有定义可选 extras，NapCat 与 Bilibili 依赖都属于当前运行时依赖。

## 验证安装

```bash
uv run python -c "from bilipy_bot.app import BotApp, RuntimeConfig; print(BotApp.__name__)"
```

预期输出：

```text
BotApp
```

也可以查看安装版本：

```bash
uv run python -c "import bilipy_bot; print(bilipy_bot.__version__)"
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

安装名是 `bilipy-bot`，导入路径是 `bilipy_bot`。应用入口从
`bilipy_bot.app` 导入，不要从 `bilipy_bot.core` 导入 `BotApp`。

## 下一步

[运行最小闭环示例](./quick-start.md)。
