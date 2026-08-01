# ButterBot 全项目模块审查与可靠性差距报告

> 审查日期：2026-08-01
> ButterBot 原始审查基线：`dev_main` / `9f920ff2f48e9659ac1e73fc1fff072a1811bc90`
> R0 整改实现基线：`dev_main` / `a676263`
> 本次复审代码基线：`dev_main` / `85d3d7c`
> R1 低风险项实现基线: `dev_main` / `65a3320`
> NcatBot 基线：本地 `dev/NcatBot-main`，包版本 `5.5.6`
> NoneBot 基线：官方 `nonebot2` 2.5.0 代码、文档与 CI
> 文档性质：当前唯一有效的项目审查基线；结论是审查时点的快照，不替代缺陷修复后的回归验收。
> **整改状态说明**：第 3～8 节保留原始基线的证据、缺陷描述和竞品比较，
> 便于追踪“为什么要改”；其中 R0 涉及的问题不能再当作当前代码现状。当前
> 结论、验收差距和下一步以本节、第 3.4～3.5 节、第 9～12 节为准。

## 可靠性整改摘要

| 工作项 | 状态 | 证据 |
| --- | --- | --- |
| R0.1 Source 所有权与生命周期 | 已完成 | `95e0643` |
| R0.2 readiness、health 与状态持久化 | 已完成 | `cd544be`、`036785a` |
| R0.3 Bilibili 弹幕受管线程 | 已完成 | `7de9b23`；保留一房间一线程 |
| R0.4 本地协议、脱敏夹具、独立覆盖率门禁 | 已完成 | `c87e401`、`98fc01d` |
| R0.5 CLI 优雅停止与失败子进程回收 | 已完成 | `98fc01d` |
| Bilibili 非法轮询间隔 | 已完成 | `a676263` |
| R1.7 稳定边界与 clean break 规则 | 已完成 | `45b3959` |
| R1.1 死代码与无用直接依赖 | 已完成 | `fde452e` |
| R1.2 日志与 terminal 所有权 | 已完成 | `836fa2c` |
| R1.3 插件作者公开面 | 已完成 | `ae67b49` |
| R1.4 运行时注册事务统一 | 已完成 | `ddbbfd0` |
| R1.5 adapter extras | 已完成 | `65a3320` |
| R1.6 类型、Lint 与半角标点门禁 | **分阶段待完成** | 本轮未加入高风险或过严门禁 |
| 二次复审发现的 P1 异步边界 | **待完成** | 插件取消静默期、WebSocket 满队列取消 |
| 24 小时长稳与真实上游联调 | **待完成** | P1 关闭后执行，仍是有限生产 Beta 的发布阻断项 |

## 1. 结论先行

原始审查基线不是“不可用”，但也不能被描述为“可靠可生产”。截至本次复审，
代码层面的 R0.1～R0.5 已完成，更准确的当前状态是：

- **核心事件框架处于 Beta**：Source 停止失败可重试，manager 不再丢弃仍有清理责任的句柄，启动部分失败会回滚。
- **NapCat 与 WebSocket 已建立有限 Beta 所需的大部分代码门槛**：首连 readiness、失败传播、退化状态、本地真实 socket 故障和 echo/背压均有回归；发送取消竞态仍须先关闭。
- **Bilibili polling 可进入受控试运行；danmaku 是 Beta 候选**：一房间一线程仍作为上游 WebSocket 缺陷的隔离边界，线程、loop、connect task 与跨线程 Future 已由 worker 管理；尚缺真实上游和 24 小时证据。
- **插件系统是“契约较成熟、生态尚未验证”**：作者公开面和注册事务已经收敛，发现、依赖排序、所有权和回滚设计值得保留；但运行时实现仍大，超时取消还有竞态，而且真实第三方插件数量不足以证明 API 已稳定。
- **CLI 已具备最小受管进程语义**：`stop` 发送 `SIGTERM` 并等待生命周期清理，`status` 聚合 Source/插件健康；旧 `close` 别名已在 clean break 中删除，它仍不是完整运维平台。

因此，当前版本适合以下范围：

- 本地开发、框架验证、受控环境中的短期任务；
- 允许人工观察和重启的单进程 NapCat/Bilibili 实验；
- 可信代码的启动期插件验证。

当前版本仍不应直接承诺以下能力：

- 无人值守长期运行；
- 未经真实 NapCat/Bilibili 环境验证的全协议兼容；
- 24 小时以上无内存、task、thread 或 session 增长；
- 热更新、不可信插件隔离、稳定插件市场或跨版本插件兼容。

本次复审没有发现新的 P0，但修正了“现在只差长稳”的乐观结论。距离“有限生产
可用”还差 **两个 P1 异步边界、EventBus 容量安全策略、24 小时长稳与真实上游
验收**。距离 NcatBot 的产品完整度仍差产品化工具；距离 NoneBot 的成熟生态仍是
长期的契约、工具链和社区积累问题，不应靠复制模块数量来追赶。

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
3. 在本次复审基线重新执行完整测试、覆盖率、Lint、格式、类型检查和构建；
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
| `core` | 21 | 1,790 | 小而清晰，依赖方向正确 |
| `app` | 7 | 2,228 | 配置、健康和生命周期集中 |
| `plugin` | 20 | 3,590 | 最大的单一子系统，约占生产代码 23% |
| `cli` | 11 | 1,919 | 进程控制已补强，配置界面仍未完成 |
| `sources/bilibili` | 24 | 2,946 | 线程生命周期已补强，仍缺真实长稳 |
| `sources/napcat` | 13 | 1,978 | 数据模型完整，本地协议回归已建立 |
| `utils` | 5 | 2,326 | WebSocket 已补强，日志和终端仍过重 |
| ButterBot 生产代码合计 | 103 | 16,797 | 仍明显小于 NcatBot |
| ButterBot 测试代码 | 70 | 12,170 | R0 后异步与协议测试显著增加 |
| NcatBot 生产代码 | 317 | 38,373 | 产品面和维护面均更大 |
| NcatBot 测试代码 | 111 | 约 17,980 | 含较完整测试工具与场景设施 |

### 3.2 ButterBot 原始基线验证结果

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

### 3.3 原始基线已确认的最小复现

三个问题已在原始基线上直接复现：

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

### 3.4 整改复审验证

原始最小复现已转化为正式回归。整改后的完整测试启用 branch coverage，并在 CI
中分别计算关键 I/O 子系统；不再允许较高的纯模型覆盖率掩盖连接和信号路径。

| 验证项 | 整改复审结果 |
| --- | --- |
| 完整 pytest | 730 passed |
| 全包 branch coverage | 84.72% |
| Bilibili 独立门禁 | 83.96% |
| NapCat 独立门禁 | 86.96% |
| WebSocket 独立门禁 | 87.27% |
| CLI runtime 独立门禁 | 82.51% |
| Ruff / format / Pyright | 全部通过，Pyright 0 error / 0 warning |
| `uv build` | wheel 与 sdist 构建成功 |

本地协议回归覆盖首连成功与失败、服务端 close、断线重连、畸形 JSON、echo
超时、监听器背压和 shutdown；Bilibili DTO/API 通过脱敏 fixture 与 fake API
离线验证。CLI 使用真实子进程验证 SIGTERM，启动登记超时路径验证
SIGTERM → bounded wait → SIGKILL → wait。

补充诊断没有直接改动质量门禁：Pyright `standard` 当前产生 12 个错误，集中在模型
override、平台分支和测试替身；Ruff 的 `ASYNC`/`PT` 分别有 19/18 项，`RUF` 全选
有 1376 项, 排除标点规则后还有 26 项. 项目决定在 R1 把自有中文文本统一为 ASCII
半角标点后启用标点规则. 这些数量用于制定 R1.6 的分批方案，不能理解成当前
basic/Ruff 门禁失败。

### 3.5 第二次复审的当前问题清单

本表描述 `65a3320` 的当前状态, 不重复第 5 节保留的 R0 前历史缺陷.

| 模块 | 当前判断 | 仍需处理的问题 |
| --- | --- | --- |
| `core` | Beta，无已知 P0 | EventBus 默认无界；`supported_types` 定义期检查仍无效；两个模型占位方法仍可能返回 `None` |
| `app` | Beta，无已知 P0/P1 所有权缺陷 | 内置 Source factory 已延迟导入 adapter; 基础 wheel 可独立运行 |
| `plugin` | Beta，存在 P1 | 作者公开面和注册事务已收敛; 生命周期回调超时后仍可能发生 `on_start` 与 `on_stop` 重叠 |
| `cli` | Beta | 只保留优雅停止的 `stop`; Source 交互配置仍是明确占位，不应宣称完整配置器 |
| Bilibili | 受控 Beta 候选 | 一房间一线程已正确保留并受管；真实上游兼容、限流和 24 小时资源曲线仍无证据 |
| NapCat | 受控 Beta 候选 | 本地协议覆盖已建立；真实 NapCat/QQ 联调仍缺失 |
| WebSocket | Beta，存在 P1 | 发送中的消息在取消时用 `await queue.put()` 回填，队列被并发填满时取消不能及时结束 |
| `utils` | 可用 | 同步 WebSocket 和 tqdm 包装已删除; `BotApp` managed 模式自动配置 root, arbitrary named logger 无需用户显式初始化 |
| 测试/CI | 强 | 730 tests、四项独立 branch 门禁、最小 wheel、adapter extra 矩阵和外部插件 smoke 通过; 尚无长稳 |
| 文档/API | Beta | 已建立 stable/provisional/internal 边界和插件作者 API snapshot; R1.6 风格与类型收敛仍待分批完成 |

第二次复审还直接复现了 WebSocket 满队列取消问题：发送任务取出第一条消息并阻塞
后，生产者填满容量为 1 的队列；对发送任务调用 `cancel()` 后，任务停在异常处理中的
`await self._send_queue.put(message)`，一次事件循环让步后仍为
`done_after_cancel=False`。这不是理论上的风格问题，应在长稳前修复。

## 4. 严重度定义

| 级别 | 定义 |
| --- | --- |
| P0 | 阻止生产使用；可能导致资源泄漏、错误的就绪状态、无法可靠关闭或关键数据路径失控 |
| P1 | 应在公开 Beta 前修复；会造成竞态、运维误操作、错误不可见或重要失败路径不可靠 |
| P2 | 可维护性、API 清晰度、冗余或长期演进问题；不一定立即导致故障 |

## 5. 逐模块审查（原始基线，R0 前）

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

   **本次复审决策调整**：ButterBot 的默认定位是拥有进程生命周期的应用框架，而
   不是永远被动嵌入的普通库。为了让 `logging.getLogger("bilibili")` 这类任意命名
   logger 在用户不显式导入配置函数时仍使用统一格式，默认运行模式可以有意识地
   管理 root logger；真正的问题改为“缺少生命周期内自动初始化、明确所有权和嵌入
   模式 opt-out”，具体方案见 R1.2。

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

### 6.1 已在 R1.1 删除

| 项目 | 原因 | 当前状态 |
| --- | --- | --- |
| `SyncWebSocketClient` | 未导出、无调用、无测试，线程安全承诺不成立 | 已删除 |
| `logging_config.py` 内自定义 `tqdm` | 未导出、无调用，制造直接依赖 | 已删除 |
| 直接依赖 `requests` | 项目无 import | 已删除 |
| 直接依赖 `pillow` | 项目无 import | 已删除; Bilibili 上游传递依赖只存在对应 extra 中 |
| 旧审查报告 | 基线和结论互相冲突 | 已由本文替代 |

### 6.2 应合并或降为内部 API

| 项目 | 建议 |
| --- | --- |
| `ExtensionRegistrar` / `PluginRegistrar` | 已提取私有事务实现并删除前者 |
| `utils/terminal.py` / `cli/terminal.py` | 已收敛为日志私有 ANSI 能力和 CLI terminal 两个职责层 |
| Bilibili dynamic/live 轮询模板 | 在回归测试完成后提取小型快照发布模板 |
| `butterbot.plugin.__all__` | 已收窄为稳定作者 API, 控制面使用具体模块或 `_internal` |
| CLI `stop` / `close` | `stop` 已统一为优雅终止; `close` 别名已删除, 不增加暂停/恢复命令 |

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
- CLI 的安装、诊断和可视化产品能力仍更弱；
- 本地协议故障测试已补齐，但真实账号与上游长稳证据仍不足；
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
| 代码体量 | 小，约 16.8k 行 | 大，约 38.4k 行 | 核心与生态拆分，不以单仓总量比较 |
| 平台抽象 | Source + Event + ApiRegistry | 多 adapter/API，但产品耦合较高 | Adapter + Bot + Event + Message + Driver |
| 插件 | 启动期可信插件、依赖与事务清理 | 插件、mixin、热重载、内置服务 | 成熟 loader、hook、matcher、DI、市场 |
| 测试门禁 | 关键 I/O 独立 branch coverage/type/build/wheel/plugin smoke | 常规测试较多，CI 无 coverage/type gate | 跨 OS/Python/Pydantic，NoneBug 行为测试 |
| 运维 | health、优雅停止和受控重启，产品诊断仍少 | 安装/诊断/测试 WebUI 更完整 | 成熟 CLI、driver 与部署生态 |
| adapter 交付 | 全部随主 wheel | 多数随主包 | 通常独立发行、按需安装 |
| 生态 | 尚未形成 | 已有实际用户路径 | 成熟社区、商店与大量 adapter/plugin |
| 当前最大风险 | 长稳证据、插件取消竞态与真实生态 | 体量、耦合、关键路径门禁 | 复杂度和兼容矩阵成本，但已有规模验证 |

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
- 已有 readiness、health 和最小结构化诊断，但部署与长期运行证据不足；
- 插件和 adapter 生态还不能验证 API 稳定性。

## 9. 距离可靠可用还有多远

以下评分已经按整改复审证据更新。0 表示缺失，3 表示有限场景可靠，5 表示经过
广泛生产验证；自动测试提升的是工程可信度，不能替代真实用户规模和长稳时间：

| 层面 | 评分 | 状态 |
| --- | ---: | --- |
| 核心事件/数据契约 | 3.5 / 5 | Beta，生命周期回归较完整，默认 callback 容量仍无界 |
| 应用与 Source 生命周期 | 4 / 5 | Beta，所有权、失败重试和回滚已修复 |
| 插件契约与发现 | 3 / 5 | Beta，控制面完整但真实生态不足 |
| 插件异常生命周期 | 2.5 / 5 | Alpha/Beta，取消竞态待修 |
| CLI 开发体验 | 3 / 5 | 默认工厂脚手架与插件流程可用 |
| CLI 运维能力 | 3 / 5 | health、SIGTERM 与失败子进程回收已覆盖 |
| NapCat 数据模型 | 3.5 / 5 | 接近 Beta |
| NapCat 连接层 | 3 / 5 | 有 readiness 与本地协议故障回归，发送取消竞态待修 |
| Bilibili polling | 3 / 5 | fixture/fake API 与状态转换已覆盖，待长稳 |
| Bilibili danmaku | 3 / 5 | 受管多线程生命周期已完成，待真实上游长稳 |
| 单元测试与 CI | 4 / 5 | 关键 I/O 各自启用 80% branch 门禁 |
| 集成/长稳/故障测试 | 2.5 / 5 | 本地协议与真实信号已补，24 小时长稳缺失 |
| 生态与兼容证明 | 0.5 / 5 | 尚未形成 |

综合判断：

- **框架内核：Beta**；
- **NapCat 单一受控部署：有限生产 Beta 候选，需先修发送取消，再完成真实联调与长稳**；
- **Bilibili polling：可进入受控试运行**；
- **Bilibili danmaku：可进入真实上游 Beta 验证，不应直接无人值守发布**；
- **整个 PyPI 发行物：R0.1～R0.5 完成，但二次复审仍有 P1，继续保持 Alpha/预发布标签**。

“追上 NcatBot”不应以 adapter 数量衡量。ButterBot 先完成 R0，再补一轮产品化工具，就能在“小而可靠的通用事件框架”这一定位上形成自己的优势。NoneBot 的差距则包括多年兼容矩阵、行为测试设施、adapter/plugin 生态和用户反馈，无法用一两个版本消除，也没有必要完全消除。

## 10. 下一步路线图

### R0：可靠性冻结版本——立即执行

此阶段停止增加 adapter、热重载、市场和新插件控制面。

> 实施进度（2026-08-01）：R0.1 已由 `95e0643` 完成；R0.2 已由
> `cd544be` 和 `036785a` 完成；R0.3 已由 `7de9b23` 完成，并保留
> “一房间一线程”作为上游 WebSocket 缺陷的隔离边界。R0.4 已加入本地
> `aiohttp` 真实 socket 回归、Bilibili 脱敏夹具与 fake API，并启用 branch
> coverage，提交为 `c87e401`；四个关键子系统的独立 80% 门禁随
> `98fc01d` 进入 CI。R0.5 同样由 `98fc01d` 完成。至此 R0 代码项全部完成，
> 但 24 小时长稳和真实上游联调尚未完成，因此还不能宣告 R0 发布验收通过。

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
3. R0 暂时保留的 `close` 别名已在 R1 clean break 中删除；
4. 后台启动失败执行完整子进程回收；
5. 添加真实子进程和信号测试；
6. 默认脚手架统一为支持插件 builder/factory 的应用工厂。

### R0 验收门槛

只有同时满足以下条件，才建议标记“有限生产 Beta”。当前状态如下：

- ✅ 本报告 P0 全部关闭，并有回归测试；
- ✅ Source 停止失败后可重试，manager 不丢失资源句柄；
- ✅ NapCat start 成功代表首次连接 ready，失败能同步传播；
- ✅ Bilibili 弹幕线程关闭不再同步阻塞主 loop；
- ✅ fake server 覆盖连接、重连、服务端关闭、取消和背压；
- ✅ Bilibili、NapCat、WebSocket、CLI runtime 的 branch coverage 均至少 80%；
- ⏳ 插件生命周期回调取消后确认静默，不与 `on_stop` 并发；
- ⏳ WebSocket 满发送队列下单次取消可以有界完成；
- ⏳ `BotApp` 的 EventBus 使用有界生产默认值并暴露 pending/limit；
- ⏳ 24 小时长稳运行无 task/thread/session 泄漏或持续内存增长趋势；
- ✅ 本地真实 SIGTERM 关闭在预算内完成，无遗留受管子进程；
- ✅ wheel 安装和三个隔离插件契约 fixture 持续通过；
- ⏳ 使用真实 NapCat 与 Bilibili 上游完成故障注入和协议兼容验收。

### R0.6：第二次复审发现的长稳前置项

以下工作不是“清理代码风格”，而是会影响可靠关闭和资源上界的 P1。应先完成，
再冻结候选提交做 24 小时长稳；否则长稳通过也不能覆盖已知竞态。

#### P1-A：插件回调取消后必须先静默，再进入停止回调

当前 [manager.py](../../butterbot/plugin/runtime/manager.py) 的
`_run_callback()` 在超时时执行 `task.cancel()` 后立即抛出 `TimeoutError`，调用方随后
执行 `on_stop()`。捕获或延迟响应 `CancelledError` 的 `on_start()` 因而可能和
`on_stop()` 同时操作同一资源。

具体修改：

1. 先添加 cancellation-resistant 插件回归：`on_start()` 捕获取消并继续等待，测试
   必须证明 `on_stop()` 不会在 `on_start()` 真正结束前进入；
2. 提取统一的 `_cancel_and_wait()`，请求取消后在 `cleanup_timeout` 预算内等待任务
   结束并消费结果，`_run_callback()`、`_run_bounded()` 和 `PluginScope._close()` 共用
   同一语义；
3. 如果宽限期后任务仍未结束，记录 `CLEANING` 超时并将插件置为不可重启的
   `FAILED`；不得对该插件并发调用 `on_stop()` 或启动同名下一代实例；
4. 框架拥有的订阅和未启动 Source 仍应撤销，但插件自有清理只能在回调任务静默后
   执行，避免以“尽力清理”为名制造并发破坏；
5. 覆盖启动超时、停止超时、二次取消、任务拒绝取消、依赖插件继续清理和应用关闭
   有界返回。

完成判据：测试事件顺序明确为 `start entered → cancel observed → start exited → stop`
或“任务未静默，跳过 stop 并隔离失败实例”，不能出现 start/stop 重叠。

#### P1-B：WebSocket 发送取消不得阻塞在满队列回填

当前 [websocket.py](../../butterbot/utils/websocket.py) 的
`_process_send_queue()` 在取消或断连时用 `await self._send_queue.put(message)` 回填。
本次复现已经证明：容量为 1 的队列在发送期间被生产者填满后，一次 `cancel()` 不能
结束发送任务。

具体修改：

1. 先把本次复现加入 `tests/utils/test_websocket.py`，断言单次取消在固定预算内完成；
2. 不在 `CancelledError` 分支执行任何可能等待容量的操作；使用由客户端持有的单一
   `_inflight_message`/retry slot 保存已出队但未确认发送的消息；
3. 重连后优先重放 retry slot，再读取普通发送队列；正常 shutdown 则清空该 slot、
   增加 dropped/failed 指标，并让相关 NapCat echo Future 明确失败；
4. 明确“连接断开前是否可能重复发送”的 at-least-once 语义；无法实现 exactly-once
   时不能用日志掩盖不确定性；
5. 覆盖队列容量 1、并发生产者、发送中断线、关闭取消、重连重放和 echo 清理。

完成判据：`stop()`、重连子任务回收和测试 teardown 都不依赖第二次取消；队列大小、
retry slot 和 pending echo 的数量都可观测且有界。

#### P1-C：给 EventBus 建立生产容量默认值

原始 `EventBus` 可继续允许显式 `None` 作为兼容的无界模式，但 `BotApp` 的生产入口
应使用有界默认值，并允许通过构造参数或运行配置覆盖。建议先以 1024 个 in-flight
callback 作为保守默认值，经压测后再调整；文档必须说明容量耗尽会让 `publish()`
等待，以及多订阅者事件可能发生部分 fan-out。

验收至少包括：默认容量生效、显式无界兼容、发布取消后的 semaphore 不泄漏、慢
owner 不影响关闭，以及状态摘要能看到 pending/limit。owner 级配额和丢弃策略可
留到 R2，不应在这一项顺便扩大调度器设计。

### R1：收敛维护面——逐项实施设计

R1 不增加 adapter、热重载、市场、暂停/恢复命令或新的插件控制面。目标是减少默认
安装、稳定导入面和重复实现，同时保持 R0 已建立的生命周期语义。每一项应独立提交，
提交中同时包含测试和文档；不得把七项合成一次大重构。

本轮已经确认四个设计决策:

| 议题 | 决策 |
| --- | --- |
| 日志 | 保留 `setup_logging()`, 由 `BotApp` 自动调用; managed 模式统一管理 root, external 模式明确 opt-out |
| aiohttp | NapCat 和 Bilibili extra 都显式声明, 不依赖上游包的传递安装 |
| 中文文本 | 内容继续使用中文, 项目自有文本的标点统一改为英文 ASCII 半角符号 |
| 当前兼容 | `3.1.0.dev2` 的 R1 是 clean break, 不保留旧 alias、warning 或转发层; R1 后的新 stable API 才开始遵守 SemVer |

截至 `65a3320`, R1.1-R1.5 和 R1.7 已完成. R1.6 保留为渐进工作流: 本轮不把
Pyright `standard`、全量半角标点扫描或未经逐条评估的 Ruff 规则加入 CI. 这不是取消
R1.6, 而是把契约修正、机械文本迁移和门禁启用拆开, 避免一次性引入高噪声改动.

#### R1.1 删除死代码和无用直接依赖

**实施状态: 已完成 (`fde452e`).** 已删除同步 WebSocket、tqdm 包装、`get_log()` 和
CLI `close`; `requests`、`pillow`、`tqdm` 不再是项目直接依赖.

当前证据：

- `SyncWebSocketClient` 只在定义文件出现，未导出、无生产调用、无测试，而且直接从
  非所属 loop 的线程读取 `asyncio.Queue`，线程安全承诺不成立；
- `logging_config.py` 的自定义 `tqdm` 没有导出或调用；
- 项目没有导入 `requests` 或 `PIL`；`pillow` 当前仅由
  `bilibili-api-python` 传递引入；
- `get_log()` 只保留旧式 warning 包装, CLI `close` 只重复当前 `stop` 的优雅停止;
- `DataPair` 有两个生产调用者，不属于死代码。

实施步骤：

1. 从 [websocket.py](../../butterbot/utils/websocket.py) 删除
   `SyncWebSocketClient`，确认模块不再为它保留同步线程生命周期代码；
2. 从 [logging_config.py](../../butterbot/utils/logging_config.py) 删除 tqdm 的可选
   import、自定义子类和样式表；
3. 从 [pyproject.toml](../../pyproject.toml) 的直接 dependencies 删除
   `requests`、`pillow`、`tqdm`，运行 `uv lock`；`pillow` 因 Bilibili 上游仍可能
   留在 lock 中，这不代表删除失败；
4. 删除 `get_log()` 和 CLI `close` 命令, 只保留标准 `logging.getLogger()` 与
   `butterbot stop`; 不增加 deprecated alias;
5. 用 `uv tree` 核对剩余包的唯一引入路径，不为“让 lock 看起来更小”覆盖上游正确
   声明；
6. 更新 `utils`/CLI 文档，不再描述已删除的同步客户端、进度条或 `close` 命令。

测试与验收：

- `rg` 对删除符号和 `close` 命令无生产/文档命中；
- 完整测试、Pyright、Ruff、构建和当前 wheel smoke 通过；
- 在干净环境安装基础 wheel 后，`pip show`/元数据中不再有三个直接要求；
- 不改动 Bilibili 一房间一线程 worker；它是必要的上游隔离，不属于本项冗余。

#### R1.2 收敛 terminal 与日志所有权

**实施状态: 已完成 (`836fa2c`).** `BotApp` 默认自动取得 managed logging lease,
任意正常传播的命名 logger 使用统一格式; `external` 模式保留宿主日志配置.

两个 terminal 文件不应机械合并成一个大文件。正确边界是：

- [cli/terminal.py](../../butterbot/cli/terminal.py) 继续只负责全副屏、按键读取和
  Click 样式，是 CLI 私有实现；
- [utils/terminal.py](../../butterbot/utils/terminal.py) 删除未使用的 RGB、256 色、
  背景色和元类开关，仅把日志确实需要的 ANSI 常量与 Windows VT 初始化收进私有
  `_ansi.py`；
- 日志模块不能反向依赖 CLI，CLI 也不应复用日志 formatter 来画界面。

`setup_logging()` 应保留, 但从“用户必须手工调用的 helper”改成框架内部与高级用户
共用的唯一实现. 日志配置按以下方式修改:

1. `BotApp.__init__()` 在解析基础配置后、实例化 Source 前自动取得 logging lease.
   普通用户只使用 `logging.getLogger("bilibili")`、`logging.getLogger(__name__)` 等
   标准 logger, 不需要 import 或调用 `setup_logging()`. 构造中途失败必须释放 lease;
2. 默认 `managed` 模式有意识地管理 root logger. 这样所有保持
   `propagate=True` 的命名 logger 都经过当前的 console/file formatter, 不要求名字
   必须位于 `butterbot.*` 下;
3. `BotApp` 新增 `logging_mode: Literal["managed", "external"] = "managed"`.
   为嵌入 FastAPI、NoneBot 或其他宿主的场景提供显式 `external` 模式; 该模式完全
   不修改 root handlers、level、formatter 或第三方 logger, 日志格式由宿主负责;
4. `setup_logging()` 返回进程级 `LoggingLease`. 第一份 lease 保存旧 root 状态并
   安装 handlers; 相同配置的后续 lease 只增加引用计数; 最后一份 lease 释放时关闭
   文件 handlers 并恢复旧 root 状态. 并存 lease 请求冲突配置时直接报错, 不静默
   重配正在运行的进程;
5. import `butterbot` 和 import `butterbot.utils` 仍保持零日志与文件系统副作用;
   构造默认 managed `BotApp` 是明确的运行时初始化边界, 可以创建日志目录和文件;
6. redirect rules 继续允许任意命名 logger, 但每个被接管 logger 的旧 level、handler
   和 propagate 状态必须由 lease 保存并在释放时恢复;
7. 保留路径逃逸校验、handler 创建失败原子回滚、颜色检测和重复初始化不累积文件
   描述符的能力. 示例删除显式 `setup_logging()` 调用, 直接展示普通 `getLogger()`.

回归测试必须覆盖: 无显式初始化启动 `BotApp` 后, `bilibili`、`NapcatApi` 和
`butterbot.*` 三类 logger 都使用当前格式; managed 模式接管并最终恢复 sentinel root
handler; external 模式从始至终不修改 sentinel; 两个应用共享同配置 lease; 冲突配置
被拒绝; 启动失败和两次 close 都不泄漏 handler; Windows/非 TTY 无颜色; CLI 全副屏
退出恢复光标.

完成判据: 默认应用运行不要求用户显式导入日志工具, 任意正常传播的命名 logger 都
使用统一格式; 嵌入者仍可通过 external 模式完全保留宿主配置; terminal 生产代码只
剩两个互不重叠的私有职责层.

#### R1.3 缩小 `butterbot.plugin` 稳定公开面

**实施状态: 已完成 (`ae67b49`).** 根门面固定为 14 个插件作者契约与可捕获异常,
框架控制面迁入具体模块或 `_internal`, API snapshot 已覆盖删除结果.

当前 `butterbot.plugin.__all__` 把插件作者契约、发现模型、bootstrap、manager、状态
记录和 registrar 收据放在同一门面。延迟导入降低了启动成本，却没有降低兼容承诺。

先在文档中冻结“作者 API”白名单：

- 基础契约：`ButterPlugin`、`PluginConfig`、`PluginContext`、
  `PluginDescriptor`；
- 声明 API：`configure`、`register`、`ConfigRegistrar`、`SourceRef`；
- 资源 API：`PluginScope`，但优先引导使用 `PluginContext.spawn/add_cleanup`；
- 作者确实需要捕获的稳定插件异常。

其余 `PluginManager`、`PluginBootstrap`、`PluginCatalog`、candidate/origin/settings、
运行状态、`PluginRegistrar`、registration receipt 和校验函数均为框架控制面。实施时：

1. 新建 `butterbot.plugin._internal` 门面供框架内部使用，生产代码先改为从具体模块或
   `_internal` 导入；
2. 控制面名称从根包 `__all__`、`__getattr__` 和 `__dir__` 一次移除, 不保留旧导入
   alias 或延迟兼容层;
3. `TYPE_CHECKING` 分支、文档示例和外部插件 fixtures 只使用作者白名单；
4. 增加 API snapshot 测试, 精确断言新的稳定 `__all__`, 并断言旧控制面不能继续从
   根包导入;
5. 状态查询若需要对应用公开，应通过 `BotApp.health` 的只读 DTO，而不是暴露整个
   `PluginManager`。

完成判据：一个普通 Handler 插件只需导入 `ButterPlugin` 与 `register`；Source
provider 最多再依赖 `configure`/`ConfigRegistrar`。框架内部控制面不再因为曾被根包
导出而被误认为稳定 API。

#### R1.4 删除 `ExtensionRegistrar`，消除重复事务实现

**实施状态: 已完成 (`ddbbfd0`).** `ExtensionRegistrar` 和旧原型文档已删除,
`PluginRegistrar` 复用私有 `_RuntimeRegistrationTransaction`.

当前不能先删 [extension.py](../../butterbot/plugin/runtime/extension.py) 再处理调用方,
因为 `PluginRegistrar` 继承它. 但本轮不需要保留公开兼容包装器, 应在同一工作项内
完成内部提取和旧入口删除:

1. 先把 Source、订阅、owner、drain 和逆序回滚提取为私有的
   `_RuntimeRegistrationTransaction`；`PluginRegistrar` 使用该实现，不再继承公开的
   `ExtensionRegistrar`；
2. 删除 `ExtensionRegistrar` 类、`extension.py`、根包导出和专属测试, 不提供 warning、
   alias 或包装器;
3. 删除或重写 `docs/extensions/prototype-foundations.md`, 推荐路径统一为
   `ButterPlugin + @configure/@register + bootstrap`；简单的无插件组装使用
   `BotApp.add_source/subscribe`；
4. 外部插件不得直接构造 `PluginRegistrar`，它仍由 manager 注入 owner；
5. 同步修改 API 文档和 fixtures, 确保仓库不再把手工事务入口描述成受支持能力.

回归覆盖：注册中途失败逆序回滚、停止失败保留 Source 句柄、取消传播、owner drain、
重复 `aclose()`, 以及 `PluginRegistrar` 只依赖新的私有事务实现.

完成判据：运行时只维护一份事务注册算法; 全仓没有 `ExtensionRegistrar` 名称和旧
原型文档; 新旧双轨维护成本归零.

#### R1.5 将 adapter 依赖改为 extras，再评估独立发行

**实施状态: 已完成 (`65a3320`).** 基础 wheel 只保留核心依赖; `napcat`、
`bilibili`、`all` 可独立安装, 缺少 extra 时返回可执行的安装命令.

先做同 wheel extras，不立即拆仓。建议基础依赖只保留 Click、Packaging、Pydantic
和 PyYAML；可选依赖定义为：

- `napcat`：`aiohttp`, NapCat 连接层直接依赖它；
- `bilibili`：`aiohttp` 与 `bilibili-api-python`. Bilibili 的 HTTP/WebSocket 运行
  路径同样需要 aiohttp, 不能只依赖上游包当前的元数据间接提供；
- `all`：当前全部内置 adapter 依赖。

代码还必须同步解耦，否则只改 `pyproject.toml` 会得到“能安装、不能构造”的假成功：

1. [source_factory.py](../../butterbot/app/source_factory.py) 的 `with_defaults()` 不能
   同时 import Bilibili 和 NapCat；改为按 factory ID 调用时才导入对应实现，或用
   adapter entry point 注册；
2. [utils 包门面](../../butterbot/utils/__init__.py) 不再无条件导入依赖 aiohttp 的
   WebSocket 模块; 内部调用改为具体模块导入, 不保留原门面的延迟兼容导出;
3. 缺少 extra 时抛出带安装命令的 `ConfigError`，例如
   `pip install 'butterbot-python[bilibili]'`，不能只暴露底层 `ModuleNotFoundError`；
4. CI 增加四类安装：基础 wheel、`[napcat]`、`[bilibili]`、`[all]`；
   基础 wheel 必须能 import `butterbot.app`、运行空 `BotApp` 和插件契约 smoke；
5. 文档所有 adapter 示例标明 extra 安装命令，锁文件和 release smoke 使用
   `--all-extras` 跑完整套件。

独立 `butterbot-adapter-*` 发行只在以下条件同时满足后进入下一阶段: 作者 API 已按
R1.3/R1.7 冻结、entry point 注册完成测试、主包不再需要 adapter 私有类型. 当前
预发布收敛窗口不保留旧的 `butterbot.sources.*` 转发层; 拆包时直接切换到新包路径,
并在同一提交更新全部文档、examples 和 fixtures.

完成判据：基础 wheel 的元数据和安装结果不含 aiohttp、Bilibili SDK、Pillow、
requests 或 tqdm；安装单个 extra 不要求另一个 adapter；全 extras 测试仍满足四项
独立覆盖率门禁。

#### R1.6 分阶段提高 Pyright 与 Ruff 门禁

**实施状态: 分阶段待完成.** 当前继续使用既有低噪声门禁. 本轮没有全仓机械转换
标点, 没有启用 Pyright `standard`, 也没有一次性启用整组 `RUF`/`PT`/`ASYNC`.
后续先修正真实类型契约并单独评审, 再逐项提高检查强度.

本次实测把 Pyright 临时切到 `standard` 后有 12 个错误，范围可控：五个 Bilibili
DTO 的 `from_raw` 返回 `None` 与基类契约不一致、`NapcatMessage.__iter__` 改写
Pydantic 迭代语义、Windows `wintypes` 三处可能未绑定，以及三个测试替身/断言类型
问题。

实施顺序：

1. 先统一 `BaseDataModel.from_raw` 契约。若兼容解析允许失败，基类与调用者都明确
   使用 `Self | None`；参数统一命名为 `raw`。两个只写 `...` 的占位方法改为抽象方法
   或明确抛错；
2. 为 `NapcatMessage` 增加 `iter_nodes()`/`message_list` 的明确接口，不再以不兼容
   签名覆盖 Pydantic `BaseModel.__iter__`; 直接删除旧迭代行为, 不保留兼容分支;
3. 把 Windows 能力封装进平台分支内返回普通 Python 类型，消除可能未绑定变量；修正
   三个测试替身，而不是用全局 `type: ignore` 压掉；
4. 切换 `typeCheckingMode = "standard"`，CI 仍要求 0 error / 0 warning。

Ruff 本次实测 `ASYNC` 19 项、`PT` 18 项、`RUF` 1376 项. `RUF` 的大头是全角中文
标点, 但本项目决定保留中文文本、统一改用英文半角符号, 因此不再忽略
`RUF001/RUF002/RUF003`. 具体执行:

1. 先做一次独立的纯机械标点提交. 人工编写的注释、docstring、日志、异常消息、CLI
   文案和 Markdown 中, `，` 改为 ASCII comma 后接空格, `。` 改为 `.`, `：` 改为
   ASCII colon 后接空格, `；` 改为 ASCII semicolon 后接空格; 括号、引号、问号、
   感叹号、顿号和省略号也使用对应 ASCII 符号;
2. 中文内容本身不翻译. 脱敏协议 fixture、上游原始 payload、必须逐字匹配的正则和
   用户数据不做替换, 因为它们不是项目排版文本, 修改会破坏协议真实性;
3. 增加半角标点检查脚本并在 CI 扫描生产代码、测试说明和文档, 对协议 fixture 使用
   明确 allowlist. 转换完成后启用 `RUF001/RUF002/RUF003`;
4. 再修复并启用 `PT` 中确认有价值的规则, 以及
   `RUF005/RUF012/RUF015/RUF022/RUF043/RUF100`;
5. `ASYNC109` 会把公开 `timeout` 参数本身视为问题, `ASYNC240` 偏向 Trio/AnyIO
   Path, 均不适合当前 asyncio API. 不启用整组, 只启用经逐条评估的规则, 并先修复
   async 测试中的 `time.sleep`;
6. 标点机械修改、类型契约修改和异步逻辑修改各自独立提交, 避免 review 时互相遮蔽.

完成判据: standard 模式全仓零错误; 项目自有中文文本只使用 ASCII 标点; Ruff 配置
不再忽略 `RUF001/RUF002/RUF003`; 新增 ignore 必须说明协议或外部数据理由, 且不允许
用批量 `noqa` 隐藏真实异步缺陷.

#### R1.7 建立 R1 收敛窗口和之后的 SemVer 边界

**实施状态: 已完成 (`45b3959`).** 已新增稳定性文档和 changelog, 本轮删除均采用
clean break, R1 后由 stable 白名单承接 SemVer 约束.

当前版本是 `3.1.0.dev2`, 还没有需要承担迁移成本的真实外部生态. R1 应被定义成
一次 clean break 收敛窗口: 只保留最终设计, 不为现有 provisional/内部入口增加
warning、alias、转发模块或双轨测试. 这项仍应最先落文档, 因为需要先列出本轮哪些
名称直接删除、哪些名称会成为 R1 后的稳定契约.

新增 API 稳定性文档和 changelog, 定义三层:

- **stable**: R1 完成后由 API 文档列出且由门面 `__all__` 导出的作者/应用契约;
- **provisional**: 明确标注的 adapter、状态 DTO 或实验能力, 可直接调整或删除;
- **internal**: 下划线命名空间和未导出控制面, 无兼容承诺.

本轮 R1 规则:

1. 删除旧 API 时不保留兼容层, 同一提交更新生产调用、tests、fixtures、examples 和
   文档;
2. API snapshot 只断言最终白名单和旧名称确实不可导入, 不测试 deprecation warning;
3. changelog 记录 clean break 的最终结果和新用法, 不维护逐版本迁移链;
4. adapter 拆分、`ExtensionRegistrar` 删除、plugin 根导出收缩和日志行为切换都遵守
   这一规则;
5. 修正 API 文档中仍写作 `3.0.2` 的版本漂移, 不再手工复制单一版本号到多处.

R1 验收并发布第一个明确标记 stable 的版本后, 新的 stable 白名单才开始遵守 SemVer:
同一 major 不做破坏性删除, provisional/internal 继续不承诺兼容. 也就是说, 当前清理
是零成本的, 但不能把“永远不兼容”延伸到未来已经形成外部插件生态的 stable API.

完成判据: 仓库只有一套新 API 和一套文档, 无旧 alias、转发模块和弃用分支; 使用者
能从稳定性文档判断 R1 后哪些名字开始受到 SemVer 保护.

### R1 执行顺序与总体验收

编号表示需求来源, 不等于实施顺序. 实际执行状态如下:

| 顺序 | 工作项 | 状态 |
| ---: | --- | --- |
| 1 | R1.7 收敛边界 | 已完成 |
| 2 | R1.1 死代码/依赖 | 已完成 |
| 3 | R1.2 日志/terminal | 已完成 |
| 4 | R1.3 -> R1.4 插件面 | 已完成 |
| 5 | R1.5 extras | 已完成; 提前完成低风险安装矩阵验收 |
| 6 | R1.6 类型/Lint | 分阶段待完成; 暂不加入高风险或高噪声规则 |

当前 R1 低风险部分验收: 基础 wheel 与各 extra 可独立安装; 730 项回归、既有
Pyright/Ruff/格式、四项独立 branch coverage、文档、build、基础/all-extras wheel
smoke 和三个外部插件 fixture 通过; managed logging 无需显式初始化且 arbitrary
named logger 使用统一格式; external logging 不修改宿主; 稳定 API snapshot 进入 CI,
仓库不存在本轮已删除入口的兼容层.

R1 尚不能标记全部完成, 唯一未完成工作项是 R1.6. 它的最终验收仍包括 Pyright
`standard`、项目自有文本半角标点检查和经逐条评估的 Ruff 规则; 在这些门禁实际启用
前, 不应把“计划通过”写成“已经通过”.

### R2：选择产品方向，而不是复制竞品

建议选择“通用事件源与内容平台自动化”作为主定位：

- 加强 Source health、重试、调度、持久化 checkpoint、事件追踪和可观测性；
- 提供类似 NoneBug/NcatBot harness 的 Source/handler 行为测试工具；
- 与 NoneBot 通过 adapter/plugin 互操作，而不是重新实现完整 matcher/DI/chat session；
- 先维护 2～3 个高质量 adapter，再扩大数量；
- 插件市场和热重载只在 API 经真实仓外插件验证后再做。

如果项目决定转为聊天机器人框架，则必须正面补齐 Bot、Message、Adapter、matcher、rule、permission、DI 和会话模型。那将是一次产品定位变更，不应伪装成普通增量需求。

## 11. 建议的执行顺序

1. ✅ 修 `BaseSource` / `SourceManager` P0，并添加回归测试；
2. ✅ 为 WebSocket/NapCat 增加 readiness 和 fake server；
3. ✅ 按受管 worker 模型加固 Bilibili danmaku，保留一房间一线程；
4. ✅ 修 CLI stop/close、状态聚合与失败子进程回收；
5. ✅ 完成 R1.7、R1.1-R1.5 的低风险收敛和独立提交;
6. **下一步: 修插件超时取消竞态与 WebSocket 满队列取消**;
7. **下一步: 给 BotApp/EventBus 建立有界生产默认值**;
8. 分批完成 R1.6, 先修真实类型契约, 再启用对应门禁;
9. 完成真实 NapCat/Bilibili 故障注入和 24 小时长稳;
10. 最后再评估 adapter 独立发行和产品化功能.

顺序的核心原则是：先让资源“能正确拥有、能知道是否 ready、能可靠关闭”，再扩展功能和生态。

## 12. 最终判断

ButterBot 的优势不是功能比 NcatBot 多，也不是生态接近 NoneBot，而是已经有一个较小、依赖方向清楚、生命周期意识较强、CI 门禁扎实的内核。这个基础值得继续投入。

原始审查中最危险的误区，是把 601 tests passed 和 77.90% coverage 等同于
生产可靠。整改后，连接就绪、线程退出、失败重试、真实信号和背压已经有直接
回归，关键 I/O 也有独立门禁；二次复审同时证明仍有 **插件取消重叠、WebSocket
满队列取消、默认容量无界** 三个长稳前置问题。其后才是 **真实上游兼容与持续
24 小时的资源稳定性**。

因此下一步不是继续堆 adapter、插件功能和 CLI 界面，而是先修复 R0.6 的三个
前置项，再冻结候选版本执行长稳与故障注入。这些证据通过后，ButterBot 才适合
标记为有明确边界的“有限生产 Beta”. R1 的低风险收敛已经提前完成; 剩余 R1.6
按“先修真实契约、再提高门禁”的方式渐进推进, 不阻塞上述可靠性前置项.
