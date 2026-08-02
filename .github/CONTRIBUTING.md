# 贡献指南

## 本页目标

搭建开发环境，运行与 CI 一致的检查，并在修改公共行为时同步文档和示例。

## 开发环境

要求：

- Python 3.12 或更高；
- uv；
- Node `^20.19.0 || >=22.0.0`；
- npm 8 或更高。

```bash
git clone https://github.com/GEYUANwuqi/ButterBot.git
cd ButterBot
uv sync --locked --dev
npm ci
```

不要提交根目录 `config.yaml`、`.env`、日志、`node_modules` 或
`docs/.vuepress/dist`。

## Python 检查

```bash
uv run pytest
uv run pytest --cov=butterbot --cov-report=term-missing --cov-fail-under=70
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv build
uv run pre-commit run --all-files
```

CI 在 Python 3.12、3.13 和 3.14 运行测试；lint、类型检查、覆盖率门槛与构建在
3.12 执行。

## 修改异步代码

至少覆盖：

- 启动成功、失败与取消；
- timeout 与异常传播；
- 重复 stop/close；
- 创建的 task、Future、listener、线程和连接均被回收；
- 测试结束没有 pending task。

测试使用 `pytest-asyncio` strict 模式。避免外部网络、固定长 sleep、全局状态
泄漏和测试顺序依赖。推荐模式见[测试异步扩展](../docs/extensions/testing.md)。

## 修改文档

开发：

```bash
npm run docs:dev
```

提交前：

```bash
npm run docs:build
npm run docs:lint
npm run docs:links
npm run docs:preview
```

`docs:preview` 用于人工预览已构建产物，结束后按 Ctrl+C。文档页面使用稳定英文
路径和中文正文。完整代码优先引用 `examples/` 中受测试文件；不能运行的代码应
明确标记为片段或外部服务示例。

新增或调整页面时同步检查：

- `docs/.vuepress/navbar.ts`；
- `docs/.vuepress/collections.ts`；
- 相关栏目 README；
- 根 README 的入口；
- 旧 URL 是否需要迁移页。

## 公共 API 变更

修改导出、签名、状态值、Data 字段、配置或异常时：

1. 更新相应 `__all__` 和类型注解；
2. 添加或更新回归测试；
3. 更新 `docs/api/`；
4. 更新指南中的完整示例；
5. 更新配置或故障排除页面；
6. 说明兼容性影响。

不要为修复文档构建而改变公共 API。

## 添加示例

- 必须包含全部导入；
- 顶层异步入口使用 `asyncio.run(main())`；
- 使用 `async with app` 或 `finally: await app.close()`；
- Source/API 回收自己创建的后台任务；
- 外部服务前置条件写在文件和文档中；
- 将示例加入 `tests/test_examples.py` 的语法或执行检查。

## Commit 与 PR

提交遵循 Conventional Commits：type 和可选 scope 使用英文，主题使用简洁中文：

```text
docs(api): 更新 BotApp 生命周期说明
fix(core): 修复关闭时的任务泄漏
```

每个提交聚焦一个逻辑改动并包含测试。PR 应说明：

- 问题与动机；
- 行为和 API 影响；
- 执行过的验证命令；
- 关联 Issue；
- 生命周期或 CLI 变更的关键日志；
- 只有视觉变化才需要截图。

## 发布说明

发布工作流只接受：

- 稳定标签 `vX.Y.Z`，且提交位于 `main`；
- 开发标签 `vX.Y.Z-dev.N`，且提交位于 `dev_main`。

标签基础版本必须与 `pyproject.toml` 一致。贡献者不要从文档流程发布包或创建
标签；发布由维护者按现有工作流执行。

## PR 前清单

- [ ] Python 测试、lint、格式化和类型检查通过
- [ ] 关键异步路径没有悬挂任务
- [ ] 文档生产构建、lint 和链接检查通过
- [ ] 示例与当前签名一致
- [ ] 没有 Secret、本地配置或构建产物
- [ ] Commit 符合项目规范
