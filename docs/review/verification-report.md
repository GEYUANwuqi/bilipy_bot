# ButterBot 架构审查验证报告

> 执行日期：2026-07-27
> 工作目录：`/home/yuan/butterbot`
> 基线提交：`d2f8699` (`dev_main`)
> 宿主：Linux，Python 3.12.3

第 2-3 节保留修改前的初次审查结果；第 6 节记录完成首批 P0/P1 后的最终复验。

## 1. 结果总览

| 检查 | 结果 | 摘要 |
| --- | --- | --- |
| 依赖同步 | 成功 | 54 个 package 已解析，53 个已检查 |
| pytest | 成功 | 修改后 383 passed |
| coverage | 成功 | 修改后总覆盖率 73.61% |
| Ruff lint | 成功 | All checks passed |
| Ruff format | 成功 | 修改后 116 files already formatted |
| Pyright | 成功 | 0 errors, 0 warnings |
| build | 成功 | sdist 和 wheel 均构建成功 |
| 文档构建 | 成功 | VuePress 渲染 45 页 |
| Markdown lint | 成功 | 原有文档 0 issues |
| 内部链接 | 成功 | 45 个 HTML 页面通过 |
| 最小示例 | 成功 | 输出 `ready` |
| wheel smoke | 成功 | 干净 venv 安装、导入、构造和关闭成功 |
| EventBus 负载复现 | 成功复现风险 | 10,000 pending task，约 11.5 MiB |
| EventBus close 取消复现 | 成功复现缺陷 | 第二次 close 仍残留 1 个 pending task |

所有正式项目检查均成功。两个最小脚本的“成功”表示成功复现审查所述行为，不表示
对应行为正确。

## 2. 执行过的命令

## 2.1 依赖同步

```bash
uv sync --locked --dev
```

结果：

```text
Resolved 54 packages in 11ms
Checked 53 packages in 12ms
```

退出码 0。没有修改 `uv.lock`。

## 2.2 完整测试

```bash
uv run pytest
```

结果：

```text
platform linux -- Python 3.12.3
collected 372 items
372 passed in 1.65s
```

pytest-asyncio 使用 `Mode.STRICT`。各测试区域均通过：

- app：BotApp、RuntimeConfig、SourceManager；
- core：context、data、event、filter、source、types、exceptions；
- sources：Bilibili polling、NapCat filters/API/source；
- utils：logging、WebSocket、DataPair；
- package import 和 examples。

## 2.3 覆盖率

```bash
uv run pytest --cov=butterbot --cov-report=term-missing
```

结果：372 passed，总计 3,643 statements，968 missed，**73%**。

核心覆盖率：

| 模块 | 覆盖率 |
| --- | --- |
| `EventBus` | 99% |
| `SubscriberGroup` | 100% |
| `SourceManager` | 98% |
| `BotApp` | 93% |
| `ApiRegistry` | 98% |
| `BaseSource` | 91% |
| `BaseDataModel` | 85% |

主要低覆盖区域：

| 模块 | 覆盖率 |
| --- | --- |
| `BilibiliApi` | 35% |
| `BiliDanmakuSource` | 30% |
| `BiliDynamicSource` | 45% |
| `BiliLiveSource` | 45% |
| `NapcatApi` | 57% |
| `utils/websocket.py` | 59% |
| `sources/napcat/events.py` | 0% |

CI 使用 `--cov-fail-under=70`；本次 73% 高于门槛。覆盖率集中度说明总数字不能替代
外部 I/O contract/integration tests。

## 2.4 Lint、格式和类型检查

执行：

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

结果：

```text
All checks passed!
114 files already formatted
0 errors, 0 warnings, 0 informations
```

三条命令退出码均为 0。

## 2.5 构建

```bash
uv build
```

结果：

```text
Successfully built dist/butterbot_python-3.1.0.dev1.tar.gz
Successfully built dist/butterbot_python-3.1.0.dev1-py3-none-any.whl
```

退出码 0。wheel metadata 中包名和版本为：

```text
Name: butterbot-python
Version: 3.1.0.dev1
Requires-Python: >=3.12
```

构建产物位于被 Git 忽略的 `dist/`。

## 2.6 文档安装和检查

执行：

```bash
npm ci
npm run docs:check
```

`npm ci` 结果：

- 安装 606 个 package；
- audit 607 个 package；
- 0 vulnerabilities；
- 有一个 `whatwg-encoding` deprecated 警告，来源于文档工具依赖。

`docs:check` 结果：

```text
VuePress build completed
Rendering 45 pages
markdownlint: 0 issues
内部链接检查通过：45 个 HTML 页面
```

退出码 0。

重要限制：

- `docs/.vuepress/config.ts` 的 `pagePatterns` 排除 `review/**`；
- `.markdownlint-cli2.mjs` 也忽略 `docs/review/**`；
- 因此本报告等审查文档不会发布到当前文档站，也不在默认 Markdown lint/生成站点
  链接门禁内；
- 最终交付额外执行独立 Markdown 结构、相对链接和 Mermaid fence 检查。

生成的 `node_modules/`、`docs/.vuepress/.temp/` 和 `docs/.vuepress/dist/` 均被 Git
忽略。

## 2.7 最小示例

执行：

```bash
uv run python examples/minimal_source_example.py
```

结果：

```text
ready
```

退出码 0。完整 pytest 也通过
`tests/test_examples.py::test_minimal_source_example_runs_and_exits_cleanly`
执行同一示例。

## 2.8 wheel 干净环境 smoke

首次尝试的命令包含删除临时目录，执行环境在进程创建前拒绝该命令：

```text
Rejected: rm -f style commands are not permitted
```

分类：**工具策略限制，不是代码、依赖或网络失败**。命令没有进入 wheel 安装逻辑。

去除清理步骤后重新执行：

```bash
tmp=$(mktemp -d /tmp/butterbot-wheel-smoke.XXXXXX)
uv venv "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" \
  /home/yuan/butterbot/dist/butterbot_python-3.1.0.dev1-py3-none-any.whl
cd "$tmp"
"$tmp/venv/bin/python" -c '
import asyncio
import butterbot
from butterbot.app import BotApp, RuntimeConfig
from butterbot.core.event import EventBus
assert butterbot.__version__ == "3.1.0.dev1"
app = BotApp(RuntimeConfig())
asyncio.run(app.close())
print(butterbot.__version__, EventBus.__name__, app.closed)
'
```

结果：

```text
Installed 34 packages
3.1.0.dev1 EventBus True
```

退出码 0。运行目录位于仓库之外，import 来自安装 wheel，而非源码树。

临时环境保留在：

```text
/tmp/butterbot-wheel-smoke.YsMI6I
```

## 3. 架构假设验证

## 3.1 EventBus 无界 pending task

方法：

- 创建一个永远等待 `asyncio.Event` 的 Handler；
- 注册到一个具体事件类型；
- 连续 `await bus.publish(...)` 10,000 次；
- 使用 `pending_callbacks` 和 `tracemalloc` 记录结果；
- 调用 `close(timeout=0)` 验证可取消回收。

结果：

```text
published=10000 pending=10000 elapsed=0.123s
current=11.49MiB peak=11.49MiB
10000 个回调在 0.0s 内未完成，强制取消
after_close pending=0
```

结论：

- **代码和运行验证证明** fan-out/in-flight task 无容量上限；
- **代码和运行验证证明** EventBus 保存强引用且正常 close 能回收；
- 该合成数据不能推导生产容量，也不能证明固定 worker pool 是最佳实现。

## 3.2 EventBus close 自身被取消

方法：

1. 发布一个已开始且被 gate 阻塞的 Handler；
2. 创建 `bus.close(timeout=30)` task；
3. 取消 close task 并观察状态；
4. 再次调用 `bus.close(timeout=0)`。

结果：

```text
after_cancel closed=True pending=1
after_second_close closed=True pending=1
```

为避免验证脚本自身遗留 task，脚本最后直接取消并 gather 内部 task。

结论：`EventBus.close()` 的 `_closed` 快速路径使取消后的清理不可重试。这是确认
缺陷，当前测试未覆盖。

## 3.3 Pydantic 公开 hook 可行性

执行了不写入仓库的最小模型试验：

- Pydantic 版本：2.13.4；
- `BaseModel.__pydantic_init_subclass__` 存在；
- 使用该 hook 实现最近 discriminator root 查找；
- 间接继承 leaf 成功注册到 root registry。

输出：

```text
{'leaf': <class '__main__.Leaf'>} True
```

这只证明替代方向可行；正式修改仍必须运行全部 BaseDataModel 和真实 NapCat 数据
回归。

## 4. 未执行项目及原因

### Python 3.13 和 3.14 本地测试

未执行。`uv python list --only-installed` 只显示 Python 3.12.3。CI 已配置 3.12、
3.13、3.14，但本报告不把 CI 配置声明当成本地运行结果。

### 真实 NapCat/Bilibili 网络测试

未执行。仓库没有测试凭证或隔离服务，测试规范要求避免外部网络。不能确认真实服务
的当前兼容性、错误率或断线恢复表现。

### `uv run pre-commit run --all-files`

未执行。仓库 pre-commit 的 Ruff hook 带 `--fix`，可能改写跟踪文件；本轮审查在
生产代码只读原则下使用等价的非改写 Ruff、format check、Pyright 和独立配置文件
检查。最终文档写入后会先运行非改写门禁并检查工作树。

### Docker/systemd smoke

未执行。仓库当前没有相应模板或标准 CLI 入口。

### 外部插件、NcatBot、NoneBot2 contract test

未执行。仓库没有这些依赖、桥接代码、目标版本或样例 distribution。

### OpenTelemetry/Prometheus 验证

未执行。项目没有相关依赖或接口。

## 5. 环境限制

- 宿主仅安装 CPython 3.12.3；
- 网络可用于依赖解析，但没有外部服务凭证；
- 工具禁止包含危险清理模式的 shell 命令；
- `docs/review/**` 被站点、默认 Markdown lint 和生成站点链接检查排除；
- `dist/`、`.coverage`、`node_modules/` 和 VuePress 输出为被忽略的验证产物；
- 审查前工作树干净。

## 6. 交付后最终复验

五份审查文档完成后已再次执行：

```bash
uv run pytest --cov=butterbot --cov-report=term-missing --cov-fail-under=70
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv build
npm run docs:check
```

结果：

- pytest：383 passed；
- coverage：73.61%，达到 70% 门槛；
- Ruff：All checks passed；
- format：116 files already formatted；
- Pyright：0 errors, 0 warnings；
- build：sdist 和 wheel 成功；
- docs：45 页构建、原有文档 lint、生成站点内部链接全部成功；
- 最新 wheel 在 `/tmp/butterbot-p0-smoke.W7yi9T` 的干净 venv 中安装成功，
  输出 `wheel-smoke 3.1.0.dev1 True`。

另对 `docs/review/*.md` 实际执行：

- Markdown fence 成对检查；
- Mermaid fence 存在且闭合；
- 相对文件链接目标检查；
- 必需章节和 Issue 字段检查；
- 直接调用 `markdownlint` 库绕过仓库 ignore，结果为 5 个文件、0 issues；
- `git diff --check`；
- `git status --short` 确认只有 `docs/review/` 下五份预期文档。
