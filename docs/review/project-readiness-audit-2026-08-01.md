# ButterBot 全项目模块审查与可靠性差距报告

> 审查日期：2026-08-01
> ButterBot 基线：`dev_main` / `9f920ff2f48e9659ac1e73fc1fff072a1811bc90`
> NcatBot 基线：本地 `dev/NcatBot-main`，包版本 `5.5.6`
> NoneBot 基线：官方 `nonebot2` 2.5.0 代码、文档与 CI
> 文档性质：当前唯一有效的项目审查基线；结论是审查时点的快照，不替代缺陷修复后的回归验收。

## 1. 结论先行

ButterBot 现在不是“不可用”，但也还不能被描述为“可靠可生产”。更准确的状态是：

- **核心事件框架处于 Beta**：事件、订阅、配置、API 注册表、主要应用编排已有较清晰的契约，测试和 CI 基础也不错。
- **作为完整发行物仍处于 Alpha**：Source 生命周期失败路径存在可复现的资源泄漏；NapCat/WebSocket 会在未连通时报告启动成功；Bilibili 弹幕源的线程、就绪和关闭模型不满足可靠异步服务要求。
- **插件系统是“契约较成熟、生态尚未验证”**：发现、依赖排序、所有权和回滚设计值得保留，但控制面偏大，超时取消还有竞态，而且真实第三方插件数量不足以证明 API 已稳定。
- **CLI 是开发者工具，不是运维控制面**：`stop` 实际发送 `SIGSTOP`，`status` 只判断进程存活，配置界面的 Source 部分仍是占位功能。

因此，当前版本适合以下范围：

- 本地开发、框架验证、受控环境中的短期任务；
- 允许人工观察和重启的单进程 NapCat/Bilibili 实验；
- 可信代码的启动期插件验证。

当前版本不应直接承诺以下能力：

- 无人值守长期运行；
- Source 启动成功即代表外部连接可用；
- 任意失败后都能无泄漏、可重试地关闭；
- Bilibili 多房间弹幕的有界异步关闭；
- 热更新、不可信插件隔离、稳定插件市场或跨版本插件兼容。

距离“有限生产可用”不是再补几个功能，而是差 **一个专门的可靠性里程碑**；距离 NcatBot 的产品完整度还差 **可靠性里程碑 + 产品化里程碑**；距离 NoneBot 的成熟生态则是长期的契约、工具链和社区积累问题，不应靠复制模块数量来追赶。

## 2. 审查范围、方法与限制

本次审查覆盖：

- `butterbot/core/`
- `butterbot/app/`
- `butterbot/plugin/`
- `butterbot/cli/`
- `butterbot/sources/bilibili/`
- `butterbot/sources/napcat/`
- `butterbot/utils/`
- 测试、CI、构建、依赖和文档结构
- 本地 `dev/NcatBot-main`
- NoneBot 官方仓库、官方文档和官方 CI

采用的方法包括：

1. 按模块阅读生产代码、公开导出、生命周期和异常路径；
2. 检查依赖方向，确认 `core` 没有反向依赖 `app` 或具体 Source；
3. 执行完整测试、覆盖率、Lint、格式、类型检查和构建；
4. 对高风险问题编写一次性最小复现，不修改生产代码；
5. 对比本地 NcatBot 的代码、测试与 CI；
6. 对 NoneBot 只使用 2.5.0 官方仓库和官方文档，不使用二手文章。

审查限制：

- 没有连接真实 Bilibili、NapCat 或 QQ 账号，避免产生外部副作用；
- 没有做安全渗透、供应链漏洞扫描和大规模性能压测；
- 本地 NcatBot 目录没有独立 `.git` 元数据，无法记录其精确 commit，只能记录包版本和文件快照；
- 本地没有 NoneBot 源码副本，因此 NoneBot 结论来自官方在线资料，不能与本地项目做逐行等价审查。

## 3. 可复现基线

### 3.1 规模

以下为 Python 文件原始行数，包含空行和注释，仅用于理解维护面，不代表质量：

| 区域 | Python 文件数 | 原始行数 | 观察 |
| --- | ---: | ---: | --- |
| `core` | 21 | 1,619 | 小而清晰，依赖方向正确 |
| `app` | 6 | 1,944 | 配置和生命周期集中 |
| `plugin` | 20 | 3,590 | 最大的单一子系统，约占生产代码 23% |
| `cli` | 11 | 1,755 | 进程控制路径测试不足 |
| `sources/bilibili` | 24 | 2,615 | DTO 较多，真实 I/O 路径最薄弱 |
| `sources/napcat` | 13 | 1,833 | 数据模型较完整，连接语义不足 |
| `utils` | 5 | 2,137 | WebSocket、日志和终端代码过重 |
| ButterBot 生产代码合计 | 约 100 | 15,513 | 仍明显小于 NcatBot |
| ButterBot 测试代码 | — | 约 9,969 | 单元测试密度较好 |
| NcatBot 生产代码 | 317 | 38,373 | 产品面和维护面均更大 |
| NcatBot 测试代码 | 111 | 约 17,980 | 含较完整测试工具与场景设施 |

### 3.2 ButterBot 验证结果

执行结果：

| 命令 | 结果 |
| --- | --- |
| `uv run pytest --cov=butterbot --cov-report=term-missing --cov-fail-under=70` | **601 passed**，总覆盖率 **77.90%** |
| `uv run ruff check .` | 通过 |
| `uv run ruff format --check .` | 通过 |
| `uv run pyright` | 0 error / 0 warning |
| `uv build` | wheel 与 sdist 构建成功 |

CI 还覆盖 Python 3.12、3.13、3.14，并执行 wheel smoke、外部插件 wheel smoke、本地目录插件和混合插件 smoke。就“合并门禁”而言，ButterBot 已经比许多同规模项目更认真。

但总覆盖率掩盖了关键路径的不均衡：

| 高风险文件 | 覆盖率 |
| --- | ---: |
| `cli/runtime.py` | 39% |
| `sources/bilibili/api/bili_api.py` | 35% |
| `sources/bilibili/source/bili_danmaku_source.py` | 31% |
| `sources/bilibili/source/bili_dynamic_source.py` | 45% |
| `sources/bilibili/source/bili_live_source.py` | 45% |
| `sources/napcat/api/napcat_api.py` | 57% |
| `utils/websocket.py` | 59% |
| `utils/logging_config.py` | 63% |

`sources/napcat/events.py` 的 0% 主要来自类型别名声明，不是重要运行时缺口，不应只看数字误判。真正的问题是连接、重连、信号、线程和真实协议边界没有达到与其风险相称的覆盖率。

### 3.3 已确认的最小复现

三个问题已在当前基线上直接复现：

```text
failed_stop: {'running': False, 'stop_calls': 1}
dynamic_close: {'running': True, 'on_stop_called': False}
poll_interval_constructor: 0

immediately_after_start: True disconnected
after_failed_connect: False closed
```

它们分别证明：

1. `BaseSource.stop()` 第一次清理失败后，第二次调用不会再执行 `on_stop()`；
2. 在 `SourceManager.start()` 前通过公开 API 启动单个 Source，`app.close()` 会清空它但不停止它；
3. Bilibili 轮询构造器接受 `0` 间隔；
4. WebSocket `start()` 在连接状态仍为 `disconnected` 时返回，连接失败稍后才异步改变运行状态。

## 4. 严重度定义

| 级别 | 定义 |
| --- | --- |
| P0 | 阻止生产使用；可能导致资源泄漏、错误的就绪状态、无法可靠关闭或关键数据路径失控 |
| P1 | 应在公开 Beta 前修复；会造成竞态、运维误操作、错误不可见或重要失败路径不可靠 |
| P2 | 可维护性、API 清晰度、冗余或长期演进问题；不一定立即导致故障 |

## 5. 逐模块审查

### 5.1 `core`：方向正确，但生命周期状态过于简化

#### 应保留的部分

- `Event`、`BaseType`、`SubscriberGroup` 和过滤器职责单一，适合继续作为稳定内核。
- `ApiRegistry` 的缓存和 `aclose_all()` 所有权清晰，关闭时采用尽力清理并聚合错误的方向正确。
- `EventBus` 会持有 callback task 强引用、记录异步异常，并在关闭时排空或取消任务；这比简单的 `create_task()` 后不管理可靠得多。
- `core` 没有导入 `app`、`plugin` 或具体 Source，符合仓库规定的依赖方向。

#### 错误与风险

1. **P0：`BaseSource.stop()` 在清理前把 `running=False`**
   文件：[base_source.py](../../butterbot/core/source/base_source.py)。`on_stop()` 抛异常或被取消后，Source 已被标记为不运行，下一次 `stop()` 会直接返回。资源可能仍存在，却失去了重试清理的入口。最小复现显示连续调用两次只执行一次 `on_stop()`。

2. **P1：启动/停止只有一个布尔值，表达不了失败和清理责任**
   `STARTING`、`STOPPING`、`FAILED_CLEANUP`、`CLOSED` 被压缩为 `running`。这正是“启动部分成功”和“停止失败”难以安全恢复的根因。至少需要独立的 `cleanup_required` 状态和生命周期锁；更稳妥的是显式状态枚举。

3. **P2：`supported_types` 子类检查无效**
   `__init_subclass__` 使用 `hasattr()`，但所有子类都会继承基类的 `supported_types=None`，所以忘记覆盖的子类不会在定义时失败，只会在订阅阶段晚失败。应检查 `cls.__dict__` 且验证为 `BaseType` 子类。

4. **P2：`BaseDataModel.from_raw()` 和 `AutoDispatchList.element_type()` 是非抽象占位体**
   文件：[base_model.py](../../butterbot/core/data/base_model.py)。方法体只有 `...`，实际会隐式返回 `None`，但类型签名承诺返回模型/类型。子类漏实现时会得到很晚且难懂的错误。应改为 `@abstractmethod` 或明确抛 `NotImplementedError`。

5. **P1：EventBus 默认无 callback 上限**
   `max_pending_callbacks` 的实现值得保留，但默认 `None` 会让慢订阅者在高流量时产生无界 task。当前上限还是全局的，一个慢 owner 可以占满全部容量。建议生产默认有界，并逐步增加 owner/source 维度的配额、丢弃/背压策略和指标。

6. **P2：有界发布的部分 fan-out 语义未明确**
   一个事件有多个订阅者时，`publish()` 可能已为前几个订阅者创建 task，随后在等待容量时被取消。此时是“部分派发”，不是原子发布。无需强行实现事务，但必须文档化并有取消回归测试。

#### 结论

`core` 不冗余，且是项目最值得保留的部分。下一步不应大改事件模型，而应先补上 Source 状态机、失败清理和有界派发语义。

### 5.2 `app`：正常路径成熟，失败路径会丢失资源所有权

#### 应保留的部分

- `RuntimeConfig` 支持 YAML、环境变量默认值和分层覆盖，职责清楚。
- `SourceFactoryRegistry` 与 `SourceCatalog` 解决配置实例化和逻辑引用，不是多余抽象；它们让插件能在不依赖具体 UUID 的情况下注册 Source 和订阅。
- `BotApp.close()` 的大顺序合理：插件 → Source → EventBus → API，嵌套 `finally` 也确保后续清理有机会执行。
- Source 批量启动失败时，会回滚已经成功启动的 Source，这是正确方向。

#### 错误与风险

1. **P0：`SourceManager.close()` 只在 manager 自身为 running 时停止 Source**
   文件：[source_manager.py](../../butterbot/app/source_manager.py)。公开的 `start_source()` 没有限制必须先启动 manager；如果调用者先单独启动 Source，manager 的 `_running` 仍为 `False`，`close()` 会直接清空字典。最小复现后 Source 仍显示 `running=True`，`on_stop()` 没有调用。

2. **P0：停止失败仍然丢弃最后一个资源句柄**
   `remove_source()` 捕获 `source.stop()` 的异常后仍在 `finally` 中退订并从目录移除，且不把停止异常返回给调用方。调用方看到“移除成功”，框架却可能留下后台线程、连接或 task。插件 registrar 也无法判断清理是否真实完成。

3. **P0：manager 停止失败后仍标记整体已停止**
   `SourceManager.stop()` 会记录单个 Source 的停止异常，然后无条件 `_running=False`。随后 `close()` 不再调用 `stop()`；叠加 `BaseSource.stop()` 的提前置位问题，失败资源几乎无法重试。

4. **P1：启动失败的当前 Source 不会获得框架级回滚**
   `BaseSource.start()` 失败后只把布尔值恢复为 false，`SourceManager` 只回滚此前完全成功的 Source。若当前 Source 的 `on_start()` 已创建部分资源再失败，必须完全依赖每个实现自行回滚。Bilibili 弹幕源当前没有做到。

5. **P2：对象入口与插件扩展配置存在能力分叉**
   [bootstrap.py](../../butterbot/plugin/runtime/bootstrap.py) 在应用已经是 `BotApp` 实例时，会忽略插件刚注册的 config builder 和 Source factory，因为实例已在模块导入阶段完成配置解析。文档已经提示必须改用工厂入口，所以这不是隐蔽 bug，但默认 `butterbot init` 生成对象入口，容易让新用户到需要插件 factory 时才被迫改形态。应让脚手架默认生成统一的工厂入口，或明确把对象入口定位为无扩展的简化模式。

#### 结论

`app` 的模块划分合理，不建议合并。必须修改的是资源所有权规则：**只要清理责任还没完成，manager 就不能把对象从自己的可恢复状态中删除。**

### 5.3 `plugin`：设计领先于生态，超时取消仍有竞态

#### 优点

- distribution entry point、本地目录和混合发现路径有确定性排序；本地发现拒绝符号链接并记录 fingerprint。
- 描述符、版本兼容、依赖拓扑、配置隔离、Source/订阅所有权和逆序回滚都有明确模型。
- CI 会构建真实外部插件 wheel 并在隔离虚拟环境 smoke，这比仅在源码树里 import 更有价值。
- `PluginScope` 统一托管插件 task 和 cleanup callback，方向正确。

#### 错误与风险

1. **P1：`on_start` 超时后立即执行 `on_stop`，可能与未结束的 `on_start` 并发**
   文件：[manager.py](../../butterbot/plugin/runtime/manager.py)。`_run_callback()` 超时后调用 `task.cancel()`，但不等待 task 确认结束就抛 `TimeoutError`；`start()` 随即把失败插件也交给 `_run_stop_callbacks()`。如果插件捕获或延迟响应 `CancelledError`，`on_start` 和 `on_stop` 会并发操作同一资源。当前超时测试只覆盖会立即响应取消的挂起协程，没有覆盖 cancellation-resistant 插件。

2. **P1：资源作用域超时只能报告，不能保证 task 已结束**
   [context.py](../../butterbot/plugin/contracts/context.py) 有界等待是必要的，但超时后的 task 可能继续运行。对于可信插件可以把“必须协作取消”写入契约；控制面还应把应用健康状态降级，并保证不会同时启动下一代同名插件。

3. **P2：公开 API 面过宽**
   `butterbot.plugin.__all__` 同时导出作者契约和框架内部控制面，包括 `PluginManager`、`PluginCatalog`、`PluginCandidate`、origin、registrar 和状态记录等。普通插件真正需要的主要是 `ButterPlugin`、descriptor/config/context、`SourceRef`、decorator 和稳定异常。过宽导出会让内部重构变成兼容性负担。

4. **P2：`ExtensionRegistrar` 是过渡性重复抽象**
   文件：[extension.py](../../butterbot/plugin/runtime/extension.py)。类文档明确它只服务手工原型，`PluginRegistrar` 又继承它提供正式插件注册。现阶段可以保留兼容，但应移入实验命名空间并设置弃用期，最终只维护一套事务注册实现。

5. **P2：子系统体量领先于真实用户验证**
   插件代码约 3,590 行，是最大单一子系统；但还没有足够外部插件、跨版本兼容数据或市场反馈证明这些公开抽象都必要。继续加热重载、沙箱或市场，会放大未经验证的维护面。

#### 结论

插件系统不是应该删除的冗余模块，但应停止扩张，先做 API 收口、超时竞态修复，并用至少两个真实仓外插件连续验证一个版本周期。

### 5.4 `cli`：开发体验已有基础，运维语义不可靠

#### 优点

- 应用入口加载、后台进程登记、Linux `/proc` 启动时间校验和 PID 复用防护有实际价值。
- `init`、`plugin list`、`plugin check`、前后台运行和 release smoke 构成了基本开发流程。
- `close` 发送 `SIGTERM`，能进入 `BotApp.run()` 的优雅关闭路径。

#### 错误与风险

1. **P1：`butterbot stop` 实际是暂停进程**
   文件：[main.py](../../butterbot/cli/main.py) 与 [runtime.py](../../butterbot/cli/runtime.py)。命令发送 `SIGSTOP`，不会关闭连接、释放锁或执行清理；用户通常理解的 stop 是终止。应删除这套暂停语义，让 `stop` 在 Source 生命周期修复完成后执行当前 `close` 的优雅终止流程；不再增加 `pause/resume` 控制面。

2. **P1：后台启动超时只 `terminate()`，不等待子进程退出**
   `_spawn_background()` 超时后不 `wait()`，也没有升级到强制终止的受控策略，可能留下短期孤儿/僵尸和残留状态。应 terminate → bounded wait → kill → wait，并验证 state token。

3. **P1：`status` 是 liveness，不是 readiness/health**
   进程活着不代表 NapCat 已连接、Bilibili 轮询成功或插件健康。状态文件至少应暴露 `starting/ready/degraded/stopping`，并聚合 Source/插件最近错误和连接状态。

4. **P2：Source 配置界面仍是占位**
   [configurator.py](../../butterbot/cli/configurator.py) 直接显示“自动发现与交互配置将在后续版本提供”。所以 `config` 不能算完成的项目配置器。

5. **P1：最危险的进程路径覆盖率只有 39%**
   缺少真实子进程级信号、后台登记超时、终止等待和 stale state 的端到端测试。Mock 单元测试不足以证明信号时序可靠。

#### 结论

CLI 不应继续增加界面功能，先修命令语义、子进程回收和健康状态。当前 `stop`/`close` 双命令是需要消除的认知冗余。

### 5.5 `sources/bilibili`：当前最大的生产风险

#### 轮询 Source

1. **P1：构造器绕过轮询间隔校验**
   [base_polling_source.py](../../butterbot/sources/bilibili/source/base_polling_source.py) 的 `set_poll_interval()` 会拒绝非正数，但 `__init__()` 直接赋值。已复现 `poll_interval=0` 被接受；有监听目标时会形成高频循环，造成 CPU 和 API 限流风险。构造和 setter 必须共用同一验证函数，并拒绝 `bool`、非有限数和非正数。

2. **P1：真实 API、DTO 和发布路径覆盖不足**
   当前测试主要验证抽象轮询节奏，没有用可控 fake API 覆盖动态、直播、异常、取消、首次快照和状态变化。API 35%、具体轮询 Source 45% 不能支撑长期运行信心。

3. **P2：动态和直播 Source 存在重复模板代码**
   两者都维护 DataPair、包装 `_poll_data`、计算状态、构造 Event、发布和重复记录异常。可以在稳定行为后提取一个小型“快照比较并发布”模板；不应在 P0/P1 修复前先做大重构。

4. **P1：DTO 宽松校验会静默吞掉上游漂移**
   `strict=False`、`extra="ignore"` 与部分 `from_raw()` 的宽泛异常捕获，使上游字段变化更可能表现为日志和丢事件，而不是明确的 adapter degraded。应保留兼容解析，但增加 fixture corpus、解析失败计数、原始事件抽样和未知字段观测。

#### 弹幕 Source

`BiliDanmakuSource` 当前应按 **原型实现** 对待，不建议小修后直接宣称生产可用：

1. **P0：每房间线程的所有权和共享状态没有完成封装**；“一房间一线程”是为了隔离上游库 WebSocket 监听缺陷，本身是当前必要的兼容边界，真正的问题是 `_loops`、`_threads` 等共享字典无同步保护，线程、loop 和连接 task 也没有统一句柄；
2. **P0：`on_start()` 不等待连接成功**，创建了 `ready` 事件却从未等待；
3. **P0：部分房间启动失败没有原子回滚**，已启动线程可能泄漏；
4. **P0：`on_stop()` 在主事件循环里调用同步 `future.result(timeout=10)` 和 `thread.join(timeout=15)`，每个房间理论上可阻塞主循环 25 秒**；
5. **P0：房间事件循环没有显式 `close()`，`connect()` task 没有被保存和回收**；
6. **P1：跨线程发布丢弃 `run_coroutine_threadsafe()` 返回的 Future，发布异常不可见，积压也不可观测**；
7. **P1：直接覆盖第三方对象 logger，线程和连接状态没有统一 health 模型**；
8. **P0：该文件覆盖率只有 31%，且没有直接的多房间/连接/关闭测试**。

推荐加固方向：保留“一房间一线程”以绕开上游库 WebSocket 监听缺陷，但把它严格封装成受管 worker。每个 worker 必须拥有自己的 loop、connect task、ready/error 结果和关闭完成信号；主 loop 只通过线程安全接口交互，并使用异步等待或 `asyncio.to_thread()` 完成关闭，不能直接执行 `Future.result()` 或 `Thread.join()`。

#### 结论

Bilibili polling 可以在补测试和参数校验后进入 Beta；弹幕 Source 需要完成受管线程生命周期加固后再评估。它不是靠把覆盖率数字补高就能解决的问题。

### 5.6 `sources/napcat` 与 `utils/websocket`：模型较好，连接契约不足

#### 优点

- NapCat 事件和消息段数据模型覆盖率高，discriminator 分发已避免生产路径再维护一套 raw dict 分支。
- echo 请求会在超时/取消时移除 pending Future，方向正确。
- WebSocket 已有重连、监听器唤醒、关闭幂等和基础指标，近期修复了断线忙等与主任务自等待问题。

#### 错误与风险

1. **P0：WebSocket `start()` 只代表 task 已创建，不代表连接已建立**
   文件：[websocket.py](../../butterbot/utils/websocket.py)。最小复现中 `await start()` 返回后 `running=True`、state 仍为 `disconnected`；连接失败后才变为 false。`NapcatSource.on_start()` 因而能向 `SourceManager` 报告成功，但服务实际上不可用。

2. **P1：NapcatClient 启动不是事务性的**
   文件：[napcat_api.py](../../butterbot/sources/napcat/api/napcat_api.py)。如果 client task 已启动而 listener 或消息 task 创建失败，没有启动回滚；直接重复调用 `start()` 还会创建新 listener/task 并覆盖旧句柄。BaseSource 的幂等保护只覆盖通过 NapcatSource 启动的常规路径，不能修复公开 API 自身的状态。

3. **P1：WebSocket 配置校验不完整**
   当前只明确验证 URI、heartbeat 和 reconnect attempts。负超时、反向 backoff、无效 jitter/compression、非正 listener/queue 限制可能晚失败或把 `0` 解释为无界队列。所有运行参数应在构造时一次验证。

4. **P2：监听器满载策略的文档和代码互相矛盾**
   `WebSocketListener.put()` 队列满时丢弃最旧消息并返回 true；`_broadcast_message()` 又声称队列满会移除 listener。正常满载下后一个分支几乎不会触发。应明确选择“drop oldest”或“evict listener”，并增加 dropped/evicted 指标。

5. **P1：发送 task 取消时重新入队可能阻塞取消**
   `_process_send_queue()` 在 `CancelledError` 时使用 `await queue.put(message)`。如果生产者在其间填满队列，取消清理会等待容量，拖住主循环 `gather()` 和重连。应使用可证明有界的 `put_nowait`/本地 pending slot，明确无法回放时的策略。

6. **P2：`SyncWebSocketClient` 是未使用且不可靠的重复包装**
   它未从 `butterbot.utils` 导出，也没有生产调用或测试；声称“所有方法线程安全”，但 `get_message_nowait()` 从调用线程直接操作属于另一个 event loop 的 `asyncio.Queue`，并且 stop 后关闭的 loop 不能再次 start。应删除，而不是为未出现的同步用例继续维护第二套生命周期。

#### 结论

NapCat 数据层接近 Beta，网络连接层仍是 Alpha。有限生产使用前必须引入本地 fake WebSocket server，测试首连、失败、重连、echo、服务端关闭、背压和关闭期间取消。

### 5.7 `utils`：历史工具代码过重，且侵入宿主应用

1. **P1：`setup_logging()` 直接替换 root logger handlers**
   文件：[logging_config.py](../../butterbot/utils/logging_config.py)。作为可嵌入库，这会移除宿主应用已有的日志配置。CLI 可以显式拥有日志策略，但库 API 应返回 handler/dictConfig 或只配置 `butterbot` logger，不应默认接管 root。

2. **P2：自定义 `tqdm` 子类是死代码**
   它没有被导出或调用，却让 `tqdm` 成为直接依赖；颜色 setter 逻辑也混淆了颜色值和属性名。删除该子类和直接依赖即可。

3. **P2：`utils/terminal.py` 与 `cli/terminal.py` 职责重叠**
   前者是 300 多行 ANSI/Windows 颜色实现，主要服务日志；后者又实现 CLI 终端交互。应收敛为一个小型平台能力层，CLI 表现优先复用 Click，日志 formatter 只保留必要颜色常量。

4. **P2：直接依赖中 `requests` 和 `pillow` 未被项目代码导入**
   应确认上游依赖声明后从直接 dependencies 删除；若只是某个 adapter 的可选能力，应进入 adapter extra，而不是污染 core 安装。

5. **应保留：`DataPair`**
   它虽小，但确实用于 Bilibili 动态/直播快照比较，没有必要为了减少文件数强行内联。未来拆 adapter 包时可随 Bilibili 内移。

### 5.8 测试、CI、打包和文档

#### 优点

- 601 个测试全部通过；异步生命周期、取消、插件回滚已经有不少有价值的回归测试。
- CI 覆盖三个 Python 版本、文档构建、类型、格式、覆盖率、wheel 和真实插件包 smoke。
- release 工作流重复执行质量门禁，不只依赖分支 CI 的历史结果。
- 测试没有依赖真实外网，结果较稳定。

#### 缺口

1. **P1：70% 聚合阈值允许关键 I/O 文件长期低于 40%**；应增加关键目录独立阈值，而不是只提高全局数字。
2. **P1：没有 branch coverage 门禁**；生命周期状态和异常分支正是本项目的主要风险。
3. **P1：缺少协议级 fake server 和故障注入**；Mock transport 不能覆盖 aiohttp session、握手、半关闭、重连时序和取消。
4. **P1：缺少长稳测试和 task 泄漏检测**；没有证明 24 小时运行后线程、task、listener、pending Future 和内存不持续增长。
5. **P2：Pyright 仍是 `basic`，Ruff 只启用 E/W/F/I**；NoneBot 已使用 `standard` 和 `ASYNC`、`PT`、`RUF` 等更贴近异步/测试风险的规则。应分阶段升级，避免一次制造大量无关改动。
6. **P2：adapter 与 core 打在同一个 wheel，并把平台依赖变成必装**；长期应拆 optional extras 或独立发行物，但应在核心契约稳定后执行。

## 6. 冗余与收敛建议

“冗余”不等于文件小，也不等于抽象多。只有重复职责、无调用者、无独立所有权价值或把内部细节误当公开 API 的代码才应删除。

### 6.1 可以尽快删除

| 项目 | 理由 | 前置验证 |
| --- | --- | --- |
| `SyncWebSocketClient` | 未导出、无调用、无测试，线程安全承诺不成立 | 全仓调用检索后删除 |
| `logging_config.py` 内自定义 `tqdm` | 未导出、无调用，制造直接依赖 | 删除后跑测试与 wheel smoke |
| 直接依赖 `requests` | 项目无 import | 检查 lock 中上游依赖后更新锁 |
| 直接依赖 `pillow` | 项目无 import | 若 Bilibili 可选能力需要，移入 extra |
| 旧审查报告 | 基线和结论互相冲突 | 已由本文替代 |

### 6.2 应合并或降为内部 API

| 项目 | 建议 |
| --- | --- |
| `ExtensionRegistrar` / `PluginRegistrar` | 保留一套事务实现；前者进入 experimental 并弃用 |
| `utils/terminal.py` / `cli/terminal.py` | 共享最小平台能力，Click 负责 CLI 样式 |
| Bilibili dynamic/live 轮询模板 | 在回归测试完成后提取小型快照发布模板 |
| `butterbot.plugin.__all__` | 分为稳定作者 API 与 `plugin.internal` 控制面 |
| CLI `stop` / `close` | 生命周期完善后让 `stop` 统一为优雅终止，`close` 作为兼容别名逐步弃用；不增加暂停/恢复命令 |

### 6.3 不应为了“减文件”删除

- `SourceCatalog`
- `SourceFactoryRegistry`
- `ApiRegistry`
- `DataPair`
- NapCat event 类型别名
- PluginScope 的资源所有权概念

这些模块有独立职责，删除只会把复杂度重新散到调用方。

## 7. 与 NcatBot 5.5.6 的对比

### 7.1 本地 NcatBot 验证事实

本地快照的 Ruff check 和 format check 通过。执行 `pytest --no-cov` 的结果是：

```text
882 collected
838 passed, 38 failed, 5 skipped, 1 xfailed
```

38 个失败都指向缺失的 `docs/docs/examples/{qq,common}`。本地快照没有 docs 子模块内容，而 NcatBot CI checkout 显式启用 `submodules: true`，因此不能把这 38 个失败直接算作 NcatBot 运行时缺陷；但它说明这个本地快照不是自包含可复现的。

NcatBot CI 会运行 Ruff、格式和 Python 3.12/3.13 测试，tag release 会 build 和 `twine check`。它的 `pyproject.toml` 配置了 branch coverage，却在 CI 中明确使用 `pytest --no-cov`；开发依赖包含 mypy，但 CI 没有类型检查步骤。相对而言，ButterBot 当前 CI 的覆盖率、Pyright、每次构建和 wheel/plugin smoke 更强。

### 7.2 能力差异

NcatBot 的优势是产品完整度：

- adapter 覆盖 NapCat、Bilibili、GitHub、Lark、AI、SnowLuma 和 mock；
- 有 QQ/Bilibili/GitHub/AI API 面；
- 有定时任务、RBAC、dispatch filter、file watcher；
- 有插件热重载；
- 有 NapCat/SnowLuma 诊断命令；
- 有测试 harness、factories、scenario DSL 和测试 WebUI；
- 从“安装、运行、诊断、开发插件、测试”形成了更完整的用户路径。

ButterBot 相对 NcatBot 的优势：

- 代码面约为其 40%，更容易建立完整心智模型；
- `core` 的依赖方向更干净，Source、EventBus、API 的所有权更明确；
- 插件依赖、注册事务、逆序回滚和隔离 wheel smoke 更系统；
- CI 有真实覆盖率门禁、类型检查和分发包安装验证；
- Source 抽象不局限于 QQ 聊天，可承载直播状态、动态和其他事件流。

ButterBot 相对 NcatBot 的缺点：

- adapter 和服务数量少，缺少诊断、测试 harness、调度、权限和可视化工具；
- 没有热重载，但当前也不应优先实现；
- CLI 运行/健康管理更弱；
- 真实连接路径测试明显不足；
- 插件控制面已经很大，实际生态却远小于 NcatBot。

NcatBot 也不是所有方面都更可靠：其生产 dependencies 中直接包含 Ruff、pre-commit、tox 等开发工具；coverage 配置排除了 NapCat adapter 和 network I/O，恰好避开最高风险路径；CI 没有 coverage/type gate。ButterBot 不应照搬其耦合规模，而应学习它的产品工作流和测试工具。

## 8. 与 NoneBot 2.5.0 的对比

NoneBot 和 ButterBot 并非完全同类：NoneBot 明确是多平台异步聊天机器人框架，ButterBot 的定位更接近通用事件源/API 自动化框架。因此，比较的目标是识别成熟框架的可靠性方法，而不是要求 ButterBot 复制全部聊天抽象。

官方 `pyproject.toml` 将 NoneBot 2.5.0 标记为 `Production/Stable`，支持 Python 3.10 到 4.0 前的版本，driver 依赖采用 optional dependencies，Pyright 使用 standard 模式，Ruff 启用了 `ASYNC`、`PT`、`RUF` 等更广规则：[NoneBot pyproject](https://raw.githubusercontent.com/nonebot/nonebot2/master/pyproject.toml)。

NoneBot 官方 CI 在 Linux、Windows、macOS 上覆盖 Python 3.10、3.11、3.12、3.13，并同时验证 Pydantic v1/v2；另有独立 Pyright 工作流：[coverage workflow](https://github.com/nonebot/nonebot2/blob/master/.github/workflows/codecov.yml)、[Pyright workflow](https://github.com/nonebot/nonebot2/blob/master/.github/workflows/pyright.yml)。

NoneBot adapter 契约明确拆分 Adapter、Bot、Event、Message，并允许一个 driver 注册多个 adapter；adapter 通常作为独立项目发布，而不是全部打入 core wheel：[使用适配器](https://nonebot.dev/docs/advanced/adapter)、[编写适配器](https://nonebot.dev/docs/developer/adapter-writing)。

NoneBug 能在隔离和集成模式下断言 matcher、rule、permission、send 和 API 调用，这是 ButterBot 当前缺少的“框架行为测试语言”：[NoneBug 行为测试](https://nonebot.dev/docs/best-practice/testing/behavior)。NoneBot 还已有正式的插件打包和发布路径：[发布插件](https://nonebot.dev/docs/developer/plugin-publishing)。

### 8.1 三项目对照

| 维度 | ButterBot | NcatBot 5.5.6 | NoneBot 2.5.0 |
| --- | --- | --- | --- |
| 核心定位 | 通用 Source/Event/API 自动化 | NapCat 为中心的多能力 SDK/产品 | 多平台聊天机器人框架 |
| 代码体量 | 小，约 15.5k 行 | 大，约 38.4k 行 | 核心与生态拆分，不以单仓总量比较 |
| 平台抽象 | Source + Event + ApiRegistry | 多 adapter/API，但产品耦合较高 | Adapter + Bot + Event + Message + Driver |
| 插件 | 启动期可信插件、依赖与事务清理 | 插件、mixin、热重载、内置服务 | 成熟 loader、hook、matcher、DI、市场 |
| 测试门禁 | coverage/type/build/wheel/plugin smoke 强 | 常规测试较多，CI 无 coverage/type gate | 跨 OS/Python/Pydantic，NoneBug 行为测试 |
| 运维 | 基础进程控制，无真实 health | 安装/诊断/测试 WebUI 更完整 | 成熟 CLI、driver 与部署生态 |
| adapter 交付 | 全部随主 wheel | 多数随主包 | 通常独立发行、按需安装 |
| 生态 | 尚未形成 | 已有实际用户路径 | 成熟社区、商店与大量 adapter/plugin |
| 当前最大风险 | 生命周期与 I/O 就绪 | 体量、耦合、关键路径门禁 | 复杂度和兼容矩阵成本，但已有规模验证 |

### 8.2 ButterBot 相对 NoneBot 的优势

- Source 抽象更通用，不强制所有事件都映射为聊天消息；
- 小内核有机会保持更低的学习和维护成本；
- 当前插件资源所有权、SourceRef 和注册事务有清晰的显式设计；
- 可以专注直播/内容平台/自动化事件，而不是在成熟聊天框架正面重复竞争。

### 8.3 ButterBot 相对 NoneBot 的缺点

- 没有统一 Bot/Message/Adapter 能力，跨聊天平台插件复用能力弱；
- 没有 matcher、rule、permission、依赖注入和会话流程这类成熟插件开发模型；
- 没有独立 adapter 发行和兼容矩阵；
- 没有 NoneBug 等行为测试工具；
- 跨 OS、Python 下限和依赖兼容范围更窄；
- 缺少 readiness、health、结构化诊断、部署和长期运行证据；
- 插件和 adapter 生态还不能验证 API 稳定性。

## 9. 距离可靠可用还有多远

以下评分是基于本次证据的工程判断，0 表示缺失，3 表示有限场景可靠，5 表示经过广泛生产验证：

| 层面 | 评分 | 状态 |
| --- | ---: | --- |
| 核心事件/数据契约 | 3.5 / 5 | Beta，结构好，需补失败语义 |
| 应用与 Source 生命周期 | 2 / 5 | Alpha，存在可复现资源所有权丢失 |
| 插件契约与发现 | 3 / 5 | Beta，控制面完整但真实生态不足 |
| 插件异常生命周期 | 2.5 / 5 | Alpha/Beta，取消竞态待修 |
| CLI 开发体验 | 2.5 / 5 | 可用但不完整 |
| CLI 运维能力 | 1.5 / 5 | liveness 与命令语义不足 |
| NapCat 数据模型 | 3.5 / 5 | 接近 Beta |
| NapCat 连接层 | 2 / 5 | Alpha，无首连就绪保证 |
| Bilibili polling | 2 / 5 | Alpha，缺少真实路径测试 |
| Bilibili danmaku | 1 / 5 | 原型，需加固受管线程生命周期 |
| 单元测试与 CI | 3.5 / 5 | 门禁较强，但分布不均 |
| 集成/长稳/故障测试 | 1 / 5 | 基本缺失 |
| 生态与兼容证明 | 0.5 / 5 | 尚未形成 |

综合判断：

- **框架内核：Beta**；
- **NapCat 单一受控部署：完成 R0 后可进入有限生产 Beta**；
- **Bilibili polling：完成 R0 后可试运行**；
- **Bilibili danmaku：受管线程生命周期加固前不进入生产范围**；
- **整个 PyPI 发行物：目前仍是 Alpha**。

“追上 NcatBot”不应以 adapter 数量衡量。ButterBot 先完成 R0，再补一轮产品化工具，就能在“小而可靠的通用事件框架”这一定位上形成自己的优势。NoneBot 的差距则包括多年兼容矩阵、行为测试设施、adapter/plugin 生态和用户反馈，无法用一两个版本消除，也没有必要完全消除。

## 10. 下一步路线图

### R0：可靠性冻结版本——立即执行

此阶段停止增加 adapter、热重载、市场和新插件控制面。

> 实施进度（2026-08-01）：R0.1 已由 `95e0643` 完成；R0.2 已由
> `cd544be` 和 `036785a` 完成代码与单元回归。WebSocket/NapCat 的
> 本地真实协议故障验证仍归 R0.4，不因 R0.2 的状态模型完成而视为
> 已获得长稳证据。R0.3 仍按“保留一房间一线程、改为受管 worker”执行。

#### R0.1 修复 Source 所有权与状态

1. 为 `BaseSource` 增加生命周期锁和显式状态，至少区分 running 与 cleanup required；
2. `on_stop()` 成功后才能清除清理责任；失败后允许重试；
3. `SourceManager.close()` 无条件扫描所有仍承担清理责任的 Source；
4. `remove_source()` 只有停止和退订成功后才删除，或要求调用者显式 `force=True`；
5. 启动部分失败的 Source 必须执行自己的回滚钩子；
6. 添加本报告四个最小复现对应的正式回归测试；
7. 覆盖并发 start/stop/close、两次取消、停止失败后重试和幂等 close。

#### R0.2 重建连接就绪与健康模型

1. WebSocket `start()` 提供明确选择：等待首次 ready，或返回可等待的 readiness Future；
2. 首连最终失败必须传播到 Source start，而不是只记日志；
3. Source 暴露 `starting/ready/degraded/stopped`、最近成功时间和最近错误；
4. NapcatClient start/stop 事务化、幂等化；
5. CLI status 聚合 Source 和插件健康，而不是只看 PID。

#### R0.3 加固 Bilibili 弹幕线程生命周期

1. 保留一房间一线程，作为上游库 WebSocket 监听缺陷的隔离边界；
2. 为每个房间建立受管 worker，统一持有 thread、loop、connect task、ready/error 和 closed 信号；
3. 有明确连接就绪和超时，多房间启动失败原子回滚；
4. 关闭过程不得在主 loop 同步执行 `Future.result()` 或 `Thread.join()`；
5. 保存并回收 connect/publish task，显式停止并关闭每个房间 loop；
6. 所有跨线程 Future 必须消费结果并记录失败。

#### R0.4 建立协议级测试

1. 本地 aiohttp fake WebSocket server；
2. 覆盖首连成功/失败、断线重连、服务端 close、畸形 JSON、echo 超时、背压和 shutdown；
3. Bilibili 使用录制后脱敏的 fixture corpus 和 fake API，不访问外网；
4. 检查每个测试结束时无未完成 asyncio task、线程和未关闭 session；
5. 对 Bilibili、NapCat、WebSocket、CLI runtime 设置独立覆盖率目标。

#### R0.5 修正 CLI 语义

1. 在 R0.1 生命周期修复完成后，让 `stop` 变为优雅停止；
2. 删除当前 `SIGSTOP` 暂停语义，不新增 `pause/resume`；
3. `close` 暂时作为兼容别名，后续按弃用政策收口；
4. 后台启动失败执行完整子进程回收；
5. 添加真实子进程和信号测试；
6. 默认脚手架统一为支持插件 builder/factory 的应用工厂。

### R0 验收门槛

只有同时满足以下条件，才建议标记“有限生产 Beta”：

- 本报告 P0 全部关闭，并有回归测试；
- Source 停止失败后可重试，manager 不丢失资源句柄；
- NapCat start 成功代表首次连接 ready，失败能同步传播；
- Bilibili 弹幕不再阻塞主 loop，或从正式支持范围暂时移除；
- fake server 覆盖连接、重连、半关闭、取消和背压；
- 关键 I/O 模块行覆盖率至少 80%，并启用 branch coverage 基线；
- 24 小时长稳运行无 task/thread/session 泄漏或持续内存增长趋势；
- SIGTERM 关闭在设定预算内完成，日志中无 `Task was destroyed`、未关闭 session 或遗留线程；
- wheel 安装和两个仓外插件契约测试持续通过。

### R1：收敛维护面

1. 删除 `SyncWebSocketClient`、自定义 tqdm 和无用直接依赖；
2. 收敛两个 terminal 模块和日志配置，避免接管宿主 root logger；
3. 缩小 `butterbot.plugin` 稳定公开面，把控制面移入 internal；
4. 弃用 `ExtensionRegistrar` 手工原型入口；
5. Bilibili/NapCat 改为 optional extras 或独立 adapter 发行；
6. Pyright 从 basic 升到 standard；Ruff 分阶段加入 `ASYNC`、`PT`、`RUF`；
7. 给公开契约建立 SemVer 和弃用政策。

### R2：选择产品方向，而不是复制竞品

建议选择“通用事件源与内容平台自动化”作为主定位：

- 加强 Source health、重试、调度、持久化 checkpoint、事件追踪和可观测性；
- 提供类似 NoneBug/NcatBot harness 的 Source/handler 行为测试工具；
- 与 NoneBot 通过 adapter/plugin 互操作，而不是重新实现完整 matcher/DI/chat session；
- 先维护 2～3 个高质量 adapter，再扩大数量；
- 插件市场和热重载只在 API 经真实仓外插件验证后再做。

如果项目决定转为聊天机器人框架，则必须正面补齐 Bot、Message、Adapter、matcher、rule、permission、DI 和会话模型。那将是一次产品定位变更，不应伪装成普通增量需求。

## 11. 建议的执行顺序

1. 修 `BaseSource` / `SourceManager` P0，并添加回归测试；
2. 为 WebSocket/NapCat 增加 readiness 和 fake server；
3. 暂停发布或按受管线程模型加固 Bilibili danmaku；
4. 修插件超时取消竞态；
5. 修 CLI stop/close 与子进程回收；
6. 完成 24 小时长稳和故障注入；
7. 再做依赖、公开 API 和终端工具的收敛；
8. 最后决定 adapter 拆包和产品化功能。

顺序的核心原则是：先让资源“能正确拥有、能知道是否 ready、能可靠关闭”，再扩展功能和生态。

## 12. 最终判断

ButterBot 的优势不是功能比 NcatBot 多，也不是生态接近 NoneBot，而是已经有一个较小、依赖方向清楚、生命周期意识较强、CI 门禁扎实的内核。这个基础值得继续投入。

当前最危险的误区是把 601 tests passed 和 77.90% coverage 等同于生产可靠。测试主要证明纯模型、正常路径和部分回滚逻辑，而真正决定机器人能否长期运行的连接就绪、线程退出、失败重试、信号和背压路径仍然薄弱。

下一版本应是可靠性版本，不是功能版本。完成 R0 后，ButterBot 可以成为一个有明确边界的“小而可靠的事件框架”；继续堆 adapter、插件功能和 CLI 界面，只会让当前的资源泄漏与可观测性缺口更难修复。
