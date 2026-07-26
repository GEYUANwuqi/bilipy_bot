# bilipy_bot 项目系统级审查报告

> 审查方式：3 个并行深度代码审查（core/app、sources/utils、tests/docs/CI）+ 本体独立验证（构建、安装、测试、类型检查、最小闭环运行、关键指控代码级复核）。所有结论均有文件:行号或命令输出支撑。
>
> 审查日期：2026-07-26｜审查基线：dev_main 分支 bee44a5 + 工作区未提交的 filters.py 语义改动

---

## 1. 执行摘要

**当前成熟度：等级 2（可以演示，但无法可靠用于真实项目），介于"技术原型"与"最小可用框架"之间。**

核心事件模型（EventBus/订阅编译/discriminator 分发/过滤器组合）设计有想法且有 243 个通过的单元测试，napcat/bilibili 两个事件源实现体量可观。但存在三条硬阻塞：

1. **不可安装、不可构建**：`pyproject.toml` 无 `[build-system]`，`uv build` 失败，`uv sync` 不安装包本体，**README 的示例命令 `uv run examples/manager_example.py` 实测直接 ModuleNotFoundError**。项目只能靠 pytest 的 `pythonpath=["."]` hack 在仓库内跑测试。
2. **异步生命周期不可靠**：EventBus 无任何关闭/排空机制；websocket 传输层存在已确认的死锁路径、stop 自我 await 导致清理跳过、首连失败不重连；弹幕源在主事件循环里同步阻塞最多 25s/房间。
3. **文档-代码-测试三方互相矛盾**：docs/SOURCE.md 教的适配方式会静默破坏框架状态管理、照抄会 ImportError；工作区有一个未提交的过滤器语义反转导致 8 个测试失败、CI 全红。

**优势**：core 无对 sources 的依赖、AppContext 实例作用域注入无全局单例、订阅编译 O(1) 派发、无硬编码凭证、yaml.safe_load、代码风格统一（ruff 全绿）。骨架值得保留，不需要重写。

---

## 2. 项目事实摘要

- **定位**：Python 3.12+ 事件驱动机器人框架（Source → EventBus → Subscriber），内置 napcat(QQ)/bilibili 两个事件源。version 3.0.2，GPL-3.0。
- **实际实现**：
  - core：Event 泛型容器、EventBus（订阅编译期展开、publish O(1) 查表、后台 task 跟踪）、BaseSource 模板方法、BaseType 层级/正则匹配、BaseDataModel 元类 discriminator 多层分发、BaseFilter &/| 组合、AppContext/ApiRegistry 注入。
  - app：BotApp 门面、SourceManager 生命周期、RuntimeConfig(yaml + builder 注册)。
  - sources：napcat（自研 ws 客户端 + 30+ pydantic 事件模型 + 21 消息段 + 6 预置过滤器 + 29 个 Event TypeAlias）；bilibili（动态/直播轮询 + 弹幕 ws 线程模型，深度耦合 bilibili-api-python）。
  - utils：1191 行 ws 客户端（async+sync）、452 行日志配置、DataPair、terminal 颜色。
- **声明但未完整实现**：
  - "可安装框架" — 实际只支持 clone 运行且示例命令跑不起来（见 §4）。
  - `SourceManager.stop()` docstring 承诺"取消所有任务"，实现中不存在（source_manager.py:189-211）。
  - NapcatApi 业务接口区块只有 `send_group_message` 一个方法（napcat_api.py:272-282），其余 OneBot 动作全缺。
  - SyncWebSocketClient（165 行）、VideoPartData、`get_all_dynamic`/`get_new_dynamic_list`、`from_type`、`events.py` 全部无生产调用方。
  - core/event、core/source、core/context、utils 四个 README 均为"--- 待施工 ---"，且被根 README 对外链接。
- **测试/文档状态**：251 用例（243 过/8 败），覆盖率 69%，但 bilibili 全包(~2000 行)、websocket(1191 行)、napcat api/source/data 零测试；docs 六篇中 SOURCE.md/TYPE.md 大面积过期。
- **CLAUDE.md 过时**：称"tests/ 目录为空"（实际 251 用例）、称 config 在 `app/config/config.py`（实际 `app/config.py`）。

## 3. 架构与运行流程

```
BotApp(RuntimeConfig) ──构造──> AppContext(config, EventBus, ApiRegistry)
        │                              ▲
        ├── add_source(Cls, **kw) ──> SourceManager._sources[uuid]
        ├── subscribe(uuid, status) ─> EventBus.add_subscriber ─编译展开─> SubscriberGroup 派发表
        └── start() ─> SourceManager.start(): 全部 bind(ctx) → 串行 await source.start()
Source.on_start → 产生数据 → ctx.bus.publish(uuid, Event)
    → SubscriberGroup.get_callbacks(uuid, status)  # O(1) 查表
    → 每回调 asyncio.create_task(wrapper)          # wrapper 内执行 event_filter.check
    → _task_done_callback 记录异常（不传播）
关闭：__aexit__ → close() → stop()(串行 on_stop) → _sources.clear()
     ⚠ EventBus 后台任务不取消不等待；ApiRegistry 资源不释放；订阅表不清
```

- 依赖方向：core→sources 无（干净）；**core→app 有 TYPE_CHECKING 反向依赖**（core/context/{app_context.py:9-10, api_registry.py:10-11} import app.config.RuntimeConfig）；**app→sources 有运行时绑定**（config.py:146-153 导入期注册 napcat/bilibili builder）。
- 扩展点：BaseSource 子类 + supported_types；BaseFilter 子类；register_builder；BaseApi.create 工厂。无 entry-points/插件发现机制。

## 4. 验证结果

| 命令 | 结果 |
|---|---|
| `uv run ruff check .` / `ruff format --check` | ✅ 全绿（95 files） |
| `uv run pytest -q` | ❌ **8 failed** / 243 passed（全部在 test_napcat_filters.py，由未提交的语义反转 diff 引起） |
| `uv run pyright` | ❌ 4 errors（同一测试文件，Mock 类不满足 Event 的 BaseDataMixin 约束） |
| `uv build` | ❌ **失败**：无 `[build-system]`，setuptools legacy 包发现报错；`git log -p` 确认历史上从未有过该段 |
| `uv pip list \| grep bilipy` | ❌ 空——`uv sync` 只装 52 个依赖，**不安装 bilipy-bot 本体**（虚拟项目模式） |
| `uv run examples/manager_example.py` | ❌ **ModuleNotFoundError: No module named 'bilipy_bot'**（README 第 41 行的原文命令） |
| 自写离线最小闭环脚本（scratchpad） | ❌ 同上 ModuleNotFoundError（包未安装；此前 `python -c` 导入成功仅因 cwd 在 sys.path） |
| `pytest --cov` | 总 69%；websocket 23%、napcat_api 31%、napcat_source 50%、bilibili 全包不在报告中（0 导入） |
| 敏感信息扫描 | ✅ 无硬编码凭证（config.yaml 与 dev/ 全为空串占位）；⚠ `.gitignore` 未忽略 `config.yaml` |
| 复核死锁指控 | ✅ websocket.py:738 `with self._listeners_lock` 内 `await _evict_oldest_listener()`(:741) → `remove_listener`(:754) 重入同一非重入锁 |
| 复核轮询语义 | ✅ bili_dynamic_source.py:218 sleep 在 per-uid 循环内 → 周期=N×interval |
| 复核 CommandFilter | ✅ `"   ".split(maxsplit=1)[0]` IndexError 实测复现（filters.py:163） |
| 阻塞项 | 无法验证真实 napcat/B站 连接（需外部服务与凭证）；结论限于代码级 |

## 5. 框架完整性判断

**未形成闭环。** 缺失环节：① 分发闭环（不可构建/安装/以包形式运行）；② 关闭闭环（EventBus 不排空、API 资源不释放、CancelledError 截断清理）；③ 订阅闭环（无退订 API、remove_source 留幽灵源与残留回调）；④ 运行时增删闭环（启动后 add_source 静默失效）；⑤ 文档闭环（适配指南教错误 API）；⑥ 错误闭环（无异常层级、配置缺失报无关 AttributeError、解析失败静默丢事件）。

## 6. 评分（0-5）

| 维度 | 分 | 依据 |
|---|---|---|
| 安装与启动 | 1 | uv build 失败；包不装入 venv；README 示例命令实测 ModuleNotFoundError |
| 核心功能完整性 | 3 | 事件链路有 243 个通过测试；但无退订、无优雅关闭、NapcatApi 业务面只有 1 个方法 |
| 架构合理性 | 3 | 注入模型与 core→sources 隔离好；core→app 反向类型依赖、app→sources 绑定、双套类型路由并存 |
| API 设计 | 2 | 门面缺 BaseSource/BaseType 导出；同包 Source 构造签名不一致；订阅无匹配时静默丢弃 |
| 类型系统 | 2 | Event[T] 全仓零参数化；RuntimeConfig 全 Any；**kwargs 吞拼写错误 |
| 异步与并发可靠性 | 1 | 已确认死锁路径、stop 自我 await、首连不重连、主循环阻塞 25s/房间、EventBus 无 drain |
| 错误处理 | 2 | 无自定义异常层级；≥10 处静默失败；启动失败仍报告 running |
| 插件与扩展能力 | 2 | 适配需 import core 且文档教法错误；register_builder 可用；无插件发现/版本契约 |
| 测试质量 | 2 | 251 用例但 8 败；异常/取消/超时/并发/shutdown 全零覆盖；websocket+bilibili 零测试；1 个无断言空壳测试 |
| 文档与示例 | 1 | SOURCE.md 教法会破坏 running 管理、照抄 ImportError；示例引用不存在的 config.example.yaml；4 个"待施工"README |
| 安全性 | 2 | 无硬编码凭证、safe_load；但默认 DEBUG 落盘全部聊天记录、token 入 dataclass repr、.gitignore 缺 config.yaml |
| 发布准备度 | 0 | 无法产出 wheel；无 py.typed；License 文件名与声明不符；release workflow 不构建不发布不跑测试 |
| 可观测性 | 2 | 日志体系存在但 import 即劫持根 logger；颜色开关实际失效；无框架级 metrics |
| 开发者体验 | 2 | ParamSpec IDE 提示好；但订阅拼错静默、配置缺失报无关错误、文档误导 |
| 长期维护性 | 2 | 双源逐行重复、三处手工同步清单、两套类型路由、多处进程级全局可变状态 |

## 7. P0 问题（阻止安装/启动/核心功能/严重风险）

### PKG-001 包不可构建、不可安装，公开文档的运行方式实测失败
- 优先级 P0｜置信度：**已确认**（命令输出）
- 证据：`pyproject.toml` 全文无 `[build-system]`（git 历史从未有过）；`uv build` 失败（setuptools legacy 包发现错误——根目录存在 examples/dev/docs/tests 多个顶层目录）；`uv sync` 后 `uv pip list` 无 bilipy-bot；`uv run examples/manager_example.py` → `ModuleNotFoundError`（examples/manager_example.py:10）。`bilipy_bot/` 与 `bilipy_bot/sources/` 均无 `__init__.py`（隐式命名空间包，setuptools 自动发现不识别）。
- 影响：项目定位"可安装框架"完全不成立；新用户按 README 部署即失败。
- 根因：pyproject 只写了 `[project]` 元数据，从未配置构建后端；顶层包缺 `__init__.py`。
- 方案：pyproject 增加 `[build-system]`（推荐 hatchling，`[tool.hatch.build.targets.wheel] packages=["bilipy_bot"]`）；为 `bilipy_bot/` 与 `bilipy_bot/sources/` 补 `__init__.py`（顶层可暴露 `__version__`）；`uv sync` 后确认包以 editable 安装进 venv。
- 涉及：pyproject.toml、bilipy_bot/__init__.py（新）、bilipy_bot/sources/__init__.py（新）
- 破坏 API：否（新增导出）｜测试：新增打包冒烟（`uv build` + 从 wheel 装入临时 venv + `python -c "import bilipy_bot.app"`）
- 验收：`uv build` 成功；`uv run examples/manager_example.py` 可 import（到达凭证/网络错误为止）；scratchpad 最小闭环脚本跑通
- 工作量：小｜依赖：无

### TEST-001 未提交的过滤器语义反转导致 8 测试失败、CI 全红、docs 空白
- 优先级 P0｜置信度：**已确认**
- 证据：`git status` 唯一改动 filters.py（宽容放行→安全拦截，filters.py:41-43,64-66,91-98,125-127,156-160,189-193）；8 个失败测试全部断言旧语义（test_napcat_filters.py:133-141,163-166,194-202,235-238,272-275,304-307）；ci.yml:36-37 无豁免 → 所有分支 push 必红；docs/FILTER.md 与 napcat/README.md:161-171 均未说明缺字段行为。
- 影响：主干工作区不可提交；CI 失去信号价值。
- 推荐：**保留 fail-closed 新语义**（方向正确），同步更新 8 个测试断言 + docs/FILTER.md + sources/napcat/README.md 说明"缺字段拦截"；同时修 pyright 4 错误（Mock 类继承 BaseDataMixin）。
- 验收：`pytest` 全绿、`pyright` 0 错、CI 绿｜工作量：小｜依赖：无

### ASYNC-001 EventBus 无关闭/排空；close 丢弃 in-flight 回调；stop docstring 与实现不符
- 优先级 P0｜置信度：**已确认**
- 证据：EventBus 全类（event_bus.py:20-194）无 close；`_background_tasks`(:28,151,183) 无任何 cancel/await 遍历；SourceManager.close(source_manager.py:213-228) 不接触 bus；stop docstring(:189-195) 声称"取消所有任务"但无实现；测试仅验证 task 跟踪（test_event_bus.py:310-357），无 shutdown 测试。
- 影响：进程退出时 pending 回调被 GC（"Task was destroyed but it is pending!"），用户回调执行到一半被掐，无 drain 语义。
- 方案：EventBus 增加 `async def close(timeout: float)` —— 先停止接受 publish，`asyncio.gather(*_background_tasks)` 带超时，超时后 cancel 并 await；SourceManager.close 在 stop sources 之后调用 bus.close；修正 docstring。
- 涉及：event_bus.py、source_manager.py｜破坏 API：否（新增）｜测试：慢回调 + close → 断言回调完成或被取消、无告警
- 验收：新增 shutdown 测试通过；`async with app` 退出后 `len(bus._background_tasks)==0`｜工作量：中｜依赖：无

### ASYNC-002 websocket 传输层确认死锁：持非重入锁跨 await 且重入
- 优先级 P0｜置信度：**已确认**（代码复核）
- 证据：websocket.py:738 `with self._listeners_lock:`（threading.Lock, :641）块内 :741 `await self._evict_oldest_listener()` → :847 `remove_listener` → :754 再次 `with self._listeners_lock` → 同线程重入非重入锁 → **事件循环永久挂死**。触发条件：listener 数达 max_listeners(1000)；`send_request` 每请求建一个 listener（napcat_api.py:144），泄漏/高并发可达。另：持 threading.Lock 跨 await 本身即错误模型。
- 方案：`_listeners_lock` 改 `asyncio.Lock`（或消除锁——单循环内 dict 操作原子）；evict 移出临界区。
- 涉及：websocket.py:641,738-759,838-874｜破坏 API：否｜测试：max_listeners=2 下连续 create_listener 不挂死
- 工作量：小｜依赖：无

### ASYNC-003 websocket stop() 自我 await 跳过全部清理；首连失败不重连；reconnect_attempts=0 语义与文档相反
- 优先级 P0｜置信度：高（代码推演，路径清晰）
- 证据：`_handle_disconnected` 超限时 `await self.stop()`(:963)，stop 内 `await self._main_task`(:704-707) 在主任务自身 → RuntimeError；此前 :700 已置 `_running=False`，finally 的 `stop()`(:936) 被 :697 早退 → :711-718 的 listener 关闭与 connection.close 全跳过 → aiohttp session 泄漏。首连在 while 外(:907)，失败直达 finally，ReconnectionStrategy 完全不生效。docstring :80,:512 称 0=无限重连，实现 `attempt_count < reconnect_attempts`(:514) → 0=立即放弃。附：listener.close() 不唤醒 queue.get 等待者(:219-227,:192)；CLOSE 帧不终止接收循环 → 0.1s 忙等永不重连(:455-456,:997-1024,:918)。
- 方案：stop 拆分"外部 stop"与"内部 shutdown"路径（内部只做清理不 await 自身）；connect 移入重连循环；修正 0 语义或文档；close 放哨兵/取消等待者；CLOSE 帧触发 _handle_disconnected。
- 涉及：websocket.py｜测试：首连失败重连、stop 后 session 关闭断言、CLOSE 帧重连｜工作量：中-大｜依赖：ASYNC-002 同文件协同改

### SEC-001 凭证误提交路径：.gitignore 未忽略 config.yaml
- 优先级 P0｜置信度：**已确认**
- 证据：.gitignore 忽略 .env/config.local.py 却无 config.yaml/config.json 条目；examples/config.yaml:5-10 与三个示例注释指引用户在仓库根创建填入 SESSDATA/token 的 config.yaml；README.md:38-41 教从仓库根运行。
- 方案：.gitignore 增加 `/config.yaml`、`config.json`；新增 `examples/config.example.yaml`（示例注释已引用此名但文件不存在）；pre-commit 加 detect-private-key。
- 工作量：小｜依赖：无

## 8. P1 问题（可靠性/架构正确性/主要 API）

### ARCH-001 运行时增删源不闭环：启动后 add_source 静默失效；remove_source 留幽灵源；无退订 API
- 置信度：已确认。证据：add_source(source_manager.py:68-94) 不检查 `_running`、不 bind 不 start；remove_source(:96-110) 只 pop 不 stop，订阅表中 uuid 回调永久残留（SubscriberGroup 无删除接口, subscriber.py:46）；BotApp/EventBus 无 unsubscribe。
- 方案：add_source 在 running 时立即 bind+start；remove_source 先 await stop 再清 `bus._subscriber_group` 对应 uuid；新增 `EventBus.remove_subscribers(uuid)` 与 `BotApp.unsubscribe`。测试：运行中动态增删源端到端。工作量：中。

### ARCH-002 启动失败状态不一致：running 先置位无回滚，manager 吞异常仍报 running
- 置信度：已确认。证据：base_source.py:65-68（`running=True` 先于 `await on_start()`）；source_manager.py:183-186（except Exception 只 log、无条件 `_running=True`）。
- 方案：on_start 失败时回滚 running=False 并从启动清单剔除或上抛聚合异常（推荐新增 `SourceStartError`）；`_log.error`→`_log.exception` 保留 traceback。用上已有但闲置的 `StubSource.start_exception` fixture（test_source_manager.py:20）。工作量：小。

### ASYNC-004 BiliDanmakuSource 线程模型阻塞主循环并泄漏 loop/task
- 置信度：已确认（行号核实）。证据：stop_room 中 `future.result(timeout=10)`(:121) + `t.join(timeout=15)`(:129) 在 async on_stop 调用链上同步阻塞主循环（N 房间线性累加）；房间 loop 从不 close(:67-68)；`create_task(danmaku.connect())` 丢引用、异常无声(:60)；`run_coroutine_threadsafe` future 丢弃 → publish 异常吞(:163-165)；`_loops` 永不清理(:47)；`ready = threading.Event()` 无人 wait（死变量,:78）。
- 方案：`await asyncio.to_thread(...)` 包裹阻塞等待；线程退出前 cancel pending + loop.close；保存 connect task 并加 done 回调记录异常；stop_room 同步清理 _loops/_danmaku_list。工作量：中。

### ASYNC-005 Ctrl+C 路径清理被截断
- 置信度：高。证据：close→stop 中 `await source.stop()`(source_manager.py:205) 在取消态抛 CancelledError，越过 `except Exception`(:207-208)，中断后续 source 清理；run()(bot_app.py:256-259) 只捕获 KeyboardInterrupt、无 SIGTERM 处理（容器下不优雅关闭）。
- 方案：stop 循环内单独 `except asyncio.CancelledError` —— 记录后继续清理其余 source，最后重抛；run() 用 `loop.add_signal_handler(SIGTERM/SIGINT)` 触发优雅关闭。工作量：小-中。

### API-001 门面不完整，适配路径与文档矛盾
- 置信度：已确认。证据：app/__init__.py 的 __all__ 仅 6 项，无 BaseSource/BaseType/BaseApi/BaseDataModel/register_builder；docs/SOURCE.md:394,429 `from bilipy_bot.core import BotApp, RuntimeConfig` 照抄 ImportError（core/__init__ 无此导出）。
- 方案：app/__init__ 补齐适配所需导出；docs 全部 import 改为 `bilipy_bot.app`。破坏 API：否（纯增）。工作量：小。

### DOCS-001 docs/SOURCE.md 教的适配方式会静默破坏框架状态管理
- 置信度：已确认。证据：docs/SOURCE.md:28-36,238,246 教覆写 abstract `start/stop`，实际基类是模板方法（base_source.py:59-79），抽象点是 on_start/on_stop(:81-93)——照文档实现会绕过 running 管理；docs/SOURCE.md:422 `asyncio.run(app.start())` 会立即退出进程（start 非阻塞）；全部 docs 未提 BotApp.run()；TYPE.md:127/131 示例正则与自身枚举值不匹配、:273-274 死链；DATA.md 缺 AutoDispatchList。
- 方案：按当前代码重写 SOURCE.md 适配章节 + 修 TYPE/DATA/FILTER 各不一致点（代理已列完整清单，逐项对照）。工作量：中。

### BUG-001 轮询间隔语义错误：周期 = N×interval
- 置信度：已确认（代码复核）。证据：bili_dynamic_source.py:203-218 / bili_live_source.py:205-220，sleep(poll_interval) 在 per-uid 循环内。监控 10 uid、interval=60 时单 uid 实际刷新 600s。
- 方案：sleep 移到整轮之后（或 interval/N 均摊）；配合 ARCH-005 抽公共轮询基类一并改。测试：假 API + 计数断言轮次节奏。工作量：小。

### BUG-002 CommandFilter 纯空白消息 IndexError
- 置信度：已确认（实测复现）。证据：filters.py:163 `text.split(maxsplit=1)[0] if text else ""`，text="   " 时 IndexError → 回调 task 异常、事件被吞。
- 方案：改 `text.split(maxsplit=1)` 先取列表再判空；补空白/空串测试。工作量：小。

### REL-001 未知 discriminator 值导致整事件静默丢失
- 置信度：已确认。证据：base_model.py:92-98 未知/缺失值一律 raise → napcat_source.py:47-49 捕获后仅 log 丢弃。NapCat 新增任一 notice_type/消息段类型（mface/markdown 等），事件永久丢失；与 NapcatType.get_specific_type 的"未知回退父类"策略（napcat_type.py:74,128,144）不一致。另：NapcatMessageData.message 强制 array 格式（event_data.py:94），messagePostFormat=string 配置下全量解析失败。
- 方案：from_dict 增加 fallback 参数（未知值降级到基类 model_validate + warning），napcat 层启用；文档注明仅支持 array 格式或增加 string 兼容。工作量：中。

### ERR-001 无异常层级；配置缺失报无关错误
- 置信度：已确认。证据：全仓仅内置异常；get_config 缺键静默 None(config.py:36) → NapcatClient.create 在 napcat_api.py:53 抛 `AttributeError: 'NoneType'...token`，与"缺少 napcat 配置"无关。
- 方案：新增 `bilipy_bot/core/exceptions.py`（BilipyError → ConfigError/SourceError/ApiError/SubscriptionError）；ApiRegistry.get_api 或各 create 对 None 配置抛 ConfigError("缺少配置键 'napcat'")；订阅无匹配（subscriber.py:75-81）从 warning 升级为 SubscriptionError（或至少可配置 strict 模式）。破坏 API：低（异常类型变化，属修复）。工作量：中。

### SEC-002 默认配置将全部聊天内容 DEBUG 落盘；token 有 repr/日志泄漏面
- 置信度：已确认。证据：FILE_LOG_LEVEL 默认 DEBUG(logging_config.py:324) + 根 DEBUG(:348)；napcat_api.py:201 `_log.debug(data)` 逐条落盘 OneBot 事件原文（QQ号/群号/聊天内容）、:138 发送消息体；websocket.py:312,336 INFO 打印完整 URI（token 在 query 时泄漏）；NapcatConfig/WebSocketConfig 均为 dataclass，repr 明文含 token/Authorization header（napcat_api.py:16-37、websocket.py:68-107）；config.py:98-99 把底层异常消息（pydantic 回显输入值）拼进 ValueError。
- 方案：FILE_LOG_LEVEL 默认 INFO；事件原文日志降为可选开关；URI 打印脱敏 query；两个 Config dataclass 加 `repr=False` 字段或自定义 __repr__；config.py 错误消息不拼原始异常文本（改 `from e` 链）。工作量：小-中。

### LIFE-001 关闭流程不释放 API 资源
- 置信度：已确认。证据：ApiRegistry 仅有 clear()(api_registry.py:50-53) 且生产零调用、无 aclose；BotApp.close 不触碰 registry；NapcatClient 持 ws 连接与 task(napcat_api.py:92,113)，若 source 未正常 stop 则常驻。另 ApiRegistry 持 threading.Lock 调用同步 create(:42-46)：阻塞循环 + create 内再 get 自死锁。
- 方案：BaseApi 增加可选 `async def aclose()`；ApiRegistry 增加 `async def aclose_all()`；BotApp.close 依次 stop sources → bus.close → registry.aclose_all；锁改 asyncio.Lock 或移除。工作量：中。依赖：ASYNC-001。

## 9. P2 问题（可维护性/测试/DX/性能）

- **TEST-002 关键路径零测试**（已确认）：回调抛异常分支(event_bus.py:158-165)、CancelledError、source.start 失败（fixture 已备未用）、BotApp.run()、超时/取消/并发/重连全零；websocket 1191 行、bilibili 全包、napcat api/source/data 零测试；空壳测试 test_napcat_filters.py:323-339（无断言）；时序断言依赖 20+ 处硬编码 `sleep(0)`；tests/sources/napcat/filters/ 缺 __init__.py；conftest 两个死 fixture；test_bot_app.py:75-78 与 test_config.py:52-55 依赖 CWD 无 config.yaml（与用户按文档操作冲突）。→ 修复方案见 §14。
- **ARCH-003 分层破坏**（已确认）：core→app TYPE_CHECKING 依赖（app_context.py:9-10 等）→ 在 core 定义 ConfigProvider Protocol，RuntimeConfig 实现之；app→sources builder 导入期注册（config.py:152-153）→ 移到 sources 各自 __init__ 或 entry-point 注册。
- **ARCH-004 双套类型路由 + 全局 registry 污染**（已确认）：NapcatType.get_specific_type（napcat_type.py:65-146 手写 30 分支）与 data 层 discriminator 平行维护；6 个 bilibili DTO 的 discriminator_value 注册进 BaseDataModel._registry 共享 dict 且从未使用（撞键风险）；元类 hasattr 恒真缺陷（base_model.py:30-35）。→ 状态判断改为从已分发的 Data 类型派生（单一真值源）；元类修正 registry 归属；删除 bilibili DTO 的无用注册。
- **ARCH-005 双轮询源逐行重复 + 构造签名不一致**（已确认）：bili_dynamic/bili_live 的 :45-59,:61-114,:191-232 几乎相同 → 抽 `BasePollingSource`；BiliDanmakuSource 用 room_id 位置参、另两个用 watch_targets → 统一。
- **TYPE-001 类型系统名不副实**：Event[T] 全仓零参数化（napcat_source.py:37 等）；RuntimeConfig 全 Any；base_source.py:46 **kwargs 吞拼写错误；subscribe 返回裸 Callable；bot_app.py:129 Any+type:ignore。→ 内部代码带头参数化 Event、get_config 加 overload/泛型、kwargs 未知键 raise。
- **UX-001 示例与配置路径**（已确认）：三示例注释引用不存在的 config.example.yaml；from_yaml 相对 CWD；napcat_example.py:180-204 死代码 periodic_task、:83-105 手写命令解析不用框架 CommandFilter、三示例 event_filter 零使用。→ 建 config.example.yaml、示例改用过滤器、from_yaml 支持显式路径提示。
- **OBS-001 日志系统侵入性副作用**（已确认）：`import bilipy_bot.utils` 即 setup_logging()（logging_config.py:415 模块级调用）→ 替换宿主根 handlers(:376)、强设 DEBUG(:348)、建 ./logs(:343)、回写环境变量(:340)；terminal.py:76 导入期改控制台模式；Color 开关对类属性访问无效（terminal.py:97-110，_COLOR=False 仍输出 ANSI）；terminal.py:136-138 未闭合 docstring 吞掉 BG_GREEN 定义（属性实际不存在）；redirect rules 文件名未校验可路径穿越(:390)；setup_logging 非幂等（重复调用 fd 泄漏）。→ 移除模块级调用（库不得自动配日志），改为显式调用 + 幂等 + 路径校验。**破坏行为**：依赖自动日志的用户需在入口显式调用（迁移说明）。
- **PERF-001 忙等与无退避**（已确认）：napcat _process_messages 在 listener 被驱逐后无 sleep 重入 while → 100% CPU（napcat_api.py:218-219 + websocket.py:873）；ws 断连 0.1s 双忙等且永不重连（websocket.py:971-973,1003-1005）；轮询源 API 连续失败无退避（412 风控下持续打脸）；send_request 高流量群 while True 空转至 60s 超时（napcat_api.py:148）。→ 异常分支加退避；send_request 按 echo 匹配专用 future 而非广播扫描。
- **CI-001**：单 job py3.12 无 3.13/3.14 matrix；无覆盖率上传；release workflow 不构建不发 PyPI 不跑测试、不校验 tag 与 version=3.0.2 一致；pre-commit 缺 detect-private-key/check-added-large-files；.coverage 未入 gitignore。

## 10. P3 问题（质量/文档/可选）

- 死代码清理：SyncWebSocketClient 165 行（含非线程安全的 get_message_nowait，与 docstring"线程安全"矛盾）、is_running、SubscriberGroup.uids、from_type、VideoPartData/Dto、get_all_dynamic/get_new_dynamic_list、DanmakuType.OFFLINE、NapcatType 死分支（napcat_source.py:43-46 恒真）、WebSocketState.Rconnecting 拼写、logging __main__ 演示块、get_log shim、examples periodic_task、events.py 未导出即孤儿（或导出它）。
- 依赖清理：requests、pillow 全库零引用（pyproject.toml:12,15）；bilibili-api-python 无上界但依赖其易变表面（LiveDanmaku 内部属性）。
- 文档补全：4 个"待施工"README、napcat README 死链/失效行号锚点、DATA.md 补 AutoDispatchList、CLAUDE.md 两处过时、License→LICENSE 更名对齐 pyproject。
- 一致性：api_registry logger 硬编码字符串脱离 bilipy_bot 层级；typing.Callable vs collections.abc 混用；DataPair 首轮必 NULL（启动时无法识别"已在直播"——按设计确认或文档化）；DataPair.get_data 可返回 None 但标注 BaseDataT（bili_dynamic_source.py:180 可产出 data=None 事件）。

## 11. 跨模块系统性问题

1. **"承诺-实现"漂移是系统性的**：stop docstring 承诺取消任务（无实现）、reconnect=0 文档说无限（实现立即放弃）、SyncWebSocketClient 自称线程安全（跨线程裸操作）、__init_subclass__ 检查恒不触发、SOURCE.md 教旧 API——同一模式在 ≥5 个模块出现。任何"文档/注释说了什么"都不能作为行为依据。
2. **静默失败是默认错误策略**：订阅无匹配、解析失败、启动失败、DTO 异常、publish 跨线程异常、未知消息类型……≥10 处只 log 或吞掉。框架级"错误可观察"通道（异常层级 + strict 模式）缺位。
3. **三处手工同步清单必然漂移**：napcat data/__init__ ↔ events.py ↔ README 表格；NapcatType.get_specific_type ↔ discriminator 值；docs ↔ 代码签名。
4. **混合并发模型无边界**：asyncio 主循环 + 弹幕房间线程/独立 loop + threading.Lock 保护 asyncio 状态 + 跨线程共享 API 单例——三种模型交叉处即是死锁/泄漏高发点（ASYNC-002/003/004 皆源于此）。

## 12. 修改路线图

### Phase 0：恢复基本可运行性（问题：PKG-001, TEST-001, SEC-001）
目标：可构建、可安装、示例可 import、测试/CI 全绿、无凭证误提交风险。
交付：pyproject [build-system] + 顶层 __init__.py；filters 测试/docs 同步 + pyright 修复；.gitignore + config.example.yaml。
验收：`uv build && uv run pytest && uv run pyright` 全绿；`uv run examples/manager_example.py` 可导入；wheel 装入临时 venv 冒烟通过。
前置：无。**工作量合计：小（1 天内）**

### Phase 1：完成核心框架闭环（ASYNC-001,002,003,005, ARCH-001,002, LIFE-001, ERR-001, BUG-001,002）
目标：启动→运行→错误→关闭全路径可靠；运行时增删源可用；异常可观察。
交付：EventBus.close + drain；websocket 锁/stop/首连重连修复；动态 add/remove/unsubscribe；异常层级 exceptions.py；轮询节奏修正；信号处理。
验收：新增 shutdown/取消/启动失败/动态增删测试全过；Ctrl+C 与 SIGTERM 下无 pending task 告警、无 Unclosed session。
前置：Phase 0。**工作量：大（核心投入）**

### Phase 2：稳定公共 API 与扩展机制（API-001, DOCS-001, REL-001, SEC-002, ARCH-003,004,005, TYPE-001）
目标：门面完整、适配文档正确、类型可用、分层干净、双源去重。
交付：app/__init__ 导出集；SOURCE/TYPE/DATA/FILTER docs 重写不一致处；discriminator 降级策略；日志脱敏与默认级别；ConfigProvider Protocol；BasePollingSource。
验收：按新 docs 从零适配一个 DemoSource 的端到端测试通过；pyright 对参数化 Event 的用例通过。
前置：Phase 1。**工作量：中-大**

### Phase 3：可靠性与测试质量（TEST-002, ASYNC-004, PERF-001, OBS-001）
目标：异常/取消/超时/重连/并发路径有测试；websocket 与弹幕源可测可靠；日志无侵入。
交付：websocket 单测（假 server/aiohttp test utils）；弹幕源线程模型重构 + 测试；退避策略；setup_logging 显式化+幂等；sleep(0) 时序断言改事件同步。
验收：覆盖率 ≥85%（websocket ≥70%）；连续 100 次全量测试无 flake。
前置：Phase 1（websocket 修复先行）。**工作量：大**

### Phase 4：发布准备（CI-001, P3 全部）
目标：可公开发布。
交付：py.typed；LICENSE 更名；CI matrix(3.12/3.13) + 覆盖率；release workflow 加 build+测试+版本一致性校验（PyPI 发布可选）；死代码/无用依赖清理；README/docs 补全；CHANGELOG。
验收：tag 触发的 release 产出可安装 wheel；新用户按 README 10 分钟跑通最小示例。
前置：Phase 0-3。**工作量：中**

## 13. 推荐的目标架构（增量，非重写）

- **保留**：Event/EventBus/SubscriberGroup 编译派发模型、BaseSource 模板方法、discriminator 元类分发、AppContext 实例注入、BotApp 门面、现有目录分层。
- **修改**：EventBus 增加生命周期（close/remove）；ApiRegistry 锁模型与 aclose；BaseSource 状态回滚；轮询源抽公共基类；日志显式初始化。
- **删除**：SyncWebSocketClient、双套类型路由中的手写分支（收敛到 discriminator）、无调用方 API、requests/pillow 依赖。
- **新增**：core/exceptions.py；core 侧 ConfigProvider Protocol（斩断 core→app）；bilipy_bot/__init__.py（版本+顶层门面）；py.typed。
- **依赖方向目标**：core 零外向依赖；app→core；sources→core(+app.config 经由 Protocol 解除)；builder 注册移入 sources 包自身。
- **生命周期所有权**：BotApp 拥有 close 全序：sources.stop → bus.close(drain) → registry.aclose_all；Source 拥有自己的 task；EventBus 拥有回调 task。

## 14. 测试补全计划

1. 单元：exceptions 层级；filters 边界（空白/空参构造）；BaseType 无点枚举值报错路径；base_model fallback 分发；DataPair None 语义。
2. 集成：DemoSource 端到端（订阅→发布→过滤→关闭）；运行中 add/remove source；启动失败回滚；订阅无匹配 strict 模式。
3. 异步：EventBus close drain/超时取消；CancelledError 传播；慢回调关闭；信号处理（可用 asyncio 测试注入）。
4. websocket：aiohttp 假服务端——首连失败重连、CLOSE 帧、listener 驱逐不死锁、stop 后无 Unclosed session、reconnect=0 语义。
5. 数据契约：napcat 真实样例 JSON 夹具驱动 30+ 模型解析（替换 dataclass Mock）；messagePostFormat=string 行为明确化。
6. 类型测试：pyright 对参数化 Event/subscribe 装饰器的正例负例（`pyright --verifytypes` 或 assert_type 用例）。
7. 打包测试：CI 中 `uv build` + 临时 venv 安装 wheel + 导入冒烟 + py.typed 存在性断言。
8. 修复既有：空壳测试补断言；死 fixture 清理；sleep(0) 改为 asyncio.Event 同步；CWD 耦合测试改用 tmp_path/monkeypatch.chdir。

## 15. 文档与发布计划

- 达到公开发布还需：正确的安装章节（pip/uv add 方式）；重写 SOURCE.md 适配指南（on_start/on_stop + run()）；4 个待施工 README；CHANGELOG；LICENSE 文件名修正；py.typed；PyPI 元数据（classifiers/urls）；release workflow 构建+发布+版本一致性校验；弃用策略说明（如日志行为变更迁移指引）。

## 16. 推荐实施顺序（前 10 个任务，严格排序）

1. **PKG-001**：pyproject 加 [build-system] + 顶层/sources __init__.py → 包可装可跑（一切验证的前提）
2. **TEST-001**：提交过滤器语义反转——同步 8 个测试断言 + docs/FILTER.md + napcat README + 修 4 个 pyright 错误 → 测试/CI 全绿
3. **SEC-001**：.gitignore 加 config.yaml/config.json + 新建 examples/config.example.yaml + pre-commit detect-private-key
4. **ASYNC-002**：websocket _listeners_lock 死锁修复（asyncio.Lock / 移出临界区）
5. **ASYNC-001**：EventBus.close(drain+timeout) + SourceManager.close 接入 + 修 stop docstring + shutdown 测试
6. **ASYNC-003**：websocket stop 自我 await / 首连重连 / reconnect=0 语义 / CLOSE 帧处理
7. **ARCH-002 + ERR-001**：启动失败回滚与异常层级（exceptions.py + 配置缺失清晰报错 + 启用闲置 fixture 补测试）
8. **ARCH-001**：动态 add/remove source 闭环 + unsubscribe API
9. **BUG-001 + BUG-002**：轮询节奏修正 + CommandFilter IndexError（各附回归测试）
10. **SEC-002**：日志默认级别 INFO + 事件原文日志开关 + URI/token 脱敏 + Config repr 遮蔽

## 17. 待确认事项

1. **过滤器语义方向**：工作区未提交 diff 改为 fail-closed（缺字段拦截）。本计划按"保留新语义、同步测试与文档"执行；若意图是实验性修改需回滚，请说明。
2. **发布目标**：是否要发布 PyPI？（当前 release workflow 只建 GitHub Release；Phase 4 的 PyPI 发布步骤按可选处理。）
3. **messagePostFormat=string 支持**：napcat 消息模型当前强制 array 格式；支持 string 是新功能还是文档声明"仅支持 array"即可？
4. **日志自动初始化**：移除 import 副作用属破坏性行为变更（依赖它的现有脚本需显式调用 setup_logging），默认按移除+迁移说明执行。
5. 无法验证真实 napcat/B站连通性（需外部服务与凭证）——传输层修复后建议用户实测一轮。

## 18. 最终结论

- **现在能否使用**：不能作为框架被第三方使用（装不上）；仓库内可跑通带外部服务的演示（绕过 README 的启动方式）。
- **适合场景**：作者本人 clone 内开发、学习事件驱动架构的参考实现。
- **不适合**：任何生产/长期运行部署（关闭不可靠、传输层有死锁与泄漏路径、错误静默）、作为依赖被安装、按公开文档上手。
- **修复到完整可用的关键工作**：Phase 0（≈1 天）解除安装与 CI 阻塞 → Phase 1（核心投入）建立可靠的启动-运行-关闭闭环 → Phase 2 修正对外 API 与文档 → Phase 3 补齐传输层测试。完成 Phase 0-2 后可达"等级 3-4：可用于内部项目"；完成全部后具备公开发布条件。

---
