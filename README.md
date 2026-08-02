# ButterBot

一个基于 Python 3.12+ 和 asyncio 的事件驱动机器人框架。项目把外部输入抽象为
Source，把数据与状态包装为 Event，再由 EventBus 分发给异步 Handler。

当前仓库内置：

- NapCat OneBot WebSocket 事件与 API；
- Bilibili 动态轮询、直播状态轮询和直播弹幕事件源；
- Source、API、Data、Type 和 Filter 扩展契约；
- 统一启动、回调排空与资源关闭流程。

## 安装与开发

```bash
uv sync --locked --dev
```

已发布 wheel 的基础安装不包含 adapter 网络依赖. 按需安装
`butterbot-python[napcat]`、`[bilibili]` 或 `[all]`;
NapCat 和 Bilibili extra 都显式包含 `aiohttp`.

运行完整 Python 检查：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## 最小示例

不依赖外部服务的示例：

```bash
uv run examples/minimal_source_example.py
```

预期输出 `ready` 并正常退出。NapCat 与 Bilibili 示例需要先复制并填写本地配置：

```bash
cp examples/config.example.yaml config.yaml
```

`config.yaml` 可能包含凭证，已被 Git 忽略，不要提交或公开。

使用 CLI 创建、配置并运行项目：

```bash
uv run butterbot init
uv run butterbot plugin
uv run butterbot plugin check
uv run butterbot run --background
uv run butterbot status
uv run butterbot stop
uv run butterbot restart
```

`run` 默认加载 `app.app` 和当前目录的 `config.yaml`。可以用位置参数或
`-path` 指定其他应用入口，用 `-config` 指定其他 YAML：

```bash
uv run butterbot run mybot.application.app -config ./deploy/config.yaml
uv run butterbot run -path mybot.application.app -config ./deploy/config.yaml
```

应用入口只负责接收 CLI 已解析的配置并返回 `BotApp`，不要在模块导入时调用
`app.run()`。

后台运行和重启语义见[命令行指南](docs/guide/cli.md)。

## 文档

本地启动 VuePress 2 + Plume 文档站：

```bash
npm install
npm run docs:dev
```

推荐入口：

- [安装](docs/guide/installation.md)
- [快速开始](docs/guide/quick-start.md)
- [核心概念](docs/concepts/README.md)
- [内置功能](docs/features/README.md)
- [扩展开发](docs/extensions/README.md)
- [API 参考](docs/api/README.md)
- [故障排除](docs/troubleshooting/README.md)
- [项目架构](docs/architecture/README.md)
- [贡献指南](.github/CONTRIBUTING.md)

生产构建与文档检查：

```bash
npm ci
npm run docs:build
npm run docs:lint
npm run docs:links
```

## 许可证

[GPL-3.0](LICENSE)

把兼容的方法去掉, 当前没有适配旧版本的焦虑
plugin进一步优化, 提供装饰器以代替注册钩子, 进一步优化Plugin*类的数量, 进一步内置插件内置方法
plugin不再引用core里的内容, 仅提供插件内容, core叫用户自己导入
