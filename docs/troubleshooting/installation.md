---
title: 安装与导入问题
---

# 安装与导入问题

## `No module named butter_bot`

可能原因：

- 未在当前环境安装；
- 命令没有通过 uv 环境运行；
- 把包名 `butter-bot` 当成导入名。

排查：

```bash
uv run python -c "import butter_bot; print(butter_bot.__version__)"
uv tree | rg butter-bot
```

修复：仓库内运行 `uv sync --locked --dev`；应用项目运行 `uv add butter-bot`。

## 无法从 `butter_bot.core` 导入 `BotApp`

这是旧文档路径。当前应用门面：

```python
from butter_bot.app import BotApp, RuntimeConfig
```

## Python 版本错误

`pyproject.toml` 要求 Python 3.12+：

```bash
uv python install 3.12
uv sync --locked --dev --python 3.12
```

## 锁文件拒绝更新

`uv sync --locked` 在依赖声明和 `uv.lock` 不一致时失败。普通使用者不要手工修改
锁文件；维护者确认依赖变化后用 uv 更新并提交声明与锁文件。

## Node 文档依赖失败

文档站要求 Node `^20.19.0 || >=22.0.0` 和 npm 8+：

```bash
node --version
npm --version
npm install
npm run docs:build
```

不要混用 npm 与其他包管理器生成第二份锁文件。
