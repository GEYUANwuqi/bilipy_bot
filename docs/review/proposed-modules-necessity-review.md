# 候选模块必要性审查

> 本文不继承候选清单中的原优先级。评分与结论以当前代码、测试和本次验证为准。
> 评分范围 1-5；复杂度、兼容风险、维护成本、过度设计风险越高越不利。

## 1. 评分总览

评分列：必要性、用户价值、可靠性收益、架构解锁、复杂度、兼容风险、维护成本、
需求证据、延迟损失、过度设计风险。

| # | 候选任务 | 必要 | 价值 | 可靠 | 解锁 | 复杂 | 兼容 | 维护 | 证据 | 延迟 | 过度 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PluginManifest/Context/RouteSpec | 2 | 2 | 1 | 4 | 4 | 5 | 5 | 2 | 1 | 5 | Split |
| 2 | EventBus worker pool + queue | 4 | 4 | 5 | 3 | 4 | 5 | 4 | 5 | 4 | 4 | Split |
| 3 | 环境变量映射与 CLI | 3 | 4 | 2 | 4 | 3 | 2 | 3 | 3 | 2 | 2 | Split |
| 4 | metrics/healthcheck/trace_id | 3 | 3 | 3 | 3 | 4 | 3 | 4 | 3 | 2 | 3 | Split |
| 5 | 去除 Pydantic 私有 API | 5 | 3 | 5 | 2 | 2 | 3 | 1 | 5 | 4 | 1 | Proceed Now |
| 6 | RBAC/PolicyEngine | 1 | 1 | 1 | 2 | 5 | 5 | 5 | 1 | 1 | 5 | Split/Reject |
| 7 | Docker/systemd | 2 | 3 | 2 | 3 | 2 | 1 | 3 | 2 | 1 | 1 | Defer |
| 8 | contract/load/release smoke | 4 | 4 | 5 | 3 | 3 | 1 | 3 | 4 | 4 | 1 | Split |
| 9 | GitHub/Webhook/Cron/Mail Source | 2 | 3 | 1 | 4 | 5 | 3 | 5 | 1 | 1 | 4 | Split/Defer |
| 10 | NcatBot/NoneBot2 桥接 | 1 | 2 | 1 | 2 | 5 | 4 | 5 | 1 | 1 | 5 | Defer |
| 11 | 目录/签名/评分/兼容矩阵 | 1 | 1 | 1 | 2 | 5 | 5 | 5 | 1 | 1 | 5 | Split/Reject |

## 2. Plugin 契约

### 2.1 当前问题是否存在

**部分存在。** 外部扩展可以通过普通 Python 包组合 Source、API、Data、Type 和
Filter，但没有统一发现、元数据、兼容声明或安装后注册入口。它是生态便利性问题，
不是当前核心运行可靠性问题。

### 2.2 仓库证据

- `BaseSource`、`BaseApi`、`BaseDataModel`、`BaseType`、`BaseFilter` 已构成事实
  扩展模型；
- `AppContext` 已提供 config、EventBus、ApiRegistry；
- `BotApp.add_source()` 和 `subscribe()` 是运行时组装入口；
- `register_builder()` 是配置扩展点；
- `docs/extensions/README.md:15-16` 明确当前无通用 Plugin 注册器；
- 仓库没有 entry point discovery、manifest schema 或第三方扩展 contract test。

### 2.3 Plugin 应表示什么

第一版若存在，Plugin 应表示**一个 Python distribution 提供的一组能力**，而不是
新的业务基类。能力可包含：

- 一个或多个 Source；
- 可选 API、Data、Type、Filter；
- 可选 Handler 注册函数；
- 可选配置 builder；
- 未来可选 ingress/adapter。

把 Plugin 定义为单个 Source 会无法表示 NapCat 的 Source+API+Data；定义为
Source+API 又排除 Handler-only 扩展。Python distribution 是发现和版本边界，
capability collection 是运行时语义。

### 2.4 PluginContext 与 AppContext

当前不应创建等价的 `PluginContext`：

- 可信扩展可直接通过注册函数接收 `BotApp` 或受文档约束的 `AppContext`；
- 复制 AppContext 会制造两个生命周期和依赖注入容器；
- 只有引入 capability policy 后，才有理由提供一个**窄化 facade**，例如只暴露
  获准的 config namespace、事件发布器和 API capability。

因此依赖方向应是未来的 `PluginContext` 包装/引用 AppContext 的受限能力，而不是
AppContext 继承 PluginContext 或二者并列持有资源。

### 2.5 RouteSpec 与订阅机制

现有路由已由 `Subscriber`、`SubscriberGroup`、`BaseType`、`BaseFilter` 和
`BotApp.subscribe()` 完成。独立公开 RouteSpec 会立即遇到：

- Source 运行时 UUID 如何在静态 manifest 中表达；
- callback 如何序列化；
- 正则和自定义 Filter 如何声明；
- 注册期展开和运行期动态 Source 如何兼容。

建议不创建通用 RouteSpec。若未来插件注册函数需要声明式返回值，可把最小
`SubscriptionSpec` 作为 provisional 辅助类型，仍由现有 EventBus 编译，不创建
第二套路由器。

### 2.6 最小 PluginManifest

仅在开始 entry point discovery 时需要，最小字段为：

| 字段 | 用途 |
| --- | --- |
| `schema_version` | manifest 自身演进 |
| `id` | 稳定、全局唯一的扩展标识 |
| `version` | 扩展版本 |
| `requires_butterbot` | ButterBot 版本范围 |
| `entrypoint` | 加载注册函数 |
| `capabilities` | 声明 source/api/handler/ingress 等能力 |

作者、主页、描述、权限说明可作为可选字段。评分、签名、下载量和运行时状态不属于
manifest v1。

### 2.7 信任和隔离

当前普通 Python 扩展必须默认视为**可信同进程代码**，它能访问文件、网络、环境
变量和所有 Python 对象。manifest 签名只能帮助确认发布者或内容未被替换，不能
阻止恶意代码。

未来若允许不可信插件，隔离边界至少是独立进程/容器、受限 IPC、显式 secret
broker、网络和文件权限、资源限额及可终止生命周期。不能声称 Python import、
RestrictedPython 或签名提供安全沙箱。

### 2.8 推荐任务拆分

#### EXT-01：provisional 扩展发现草案

- **目标：** 用 Python entry point 发现 distribution 注册函数，并定义最小
  manifest/capability 描述。
- **非目标：** 稳定公共协议、市场、权限沙箱、远程安装。
- **依赖：** 配置来源规范；最好先有 capability vocabulary。
- **主要范围：** 独立 extension 模块、entry point loader、错误隔离、样例外部包。
- **公共 API：** 仅 provisional/internal 命名空间，不从稳定顶层导出。
- **验收：** Source+API、Handler-only、ingress adapter 三种样例可加载和卸载；
  单个加载失败不破坏其他扩展。
- **测试：** 干净环境安装、重复加载、版本不兼容、注册失败和关闭测试。
- **文档：** 信任模型、生命周期、兼容声明。
- **风险：** 过早固化注册函数和 manifest。
- **回滚：** 删除 provisional loader，普通 Python 组装仍可用。
- **优先级：** P2，**Design Only/试验实现**。

#### EXT-02：稳定发布插件协议

- **前置条件：** 至少 3 个独立维护的外部 distribution，覆盖上述三种能力形态，
  并经历至少两个 ButterBot 小版本。
- **公共 API：** 届时才进入稳定命名空间并承诺弃用周期。
- **优先级：** P3；条件不满足时不排期。

### 2.9 最终结论

**Split。** 当前只允许 provisional 设计和外部验证；正式稳定发布不是 P0。
PluginContext 暂不创建，RouteSpec 合并到未来最小订阅声明或 Reject。

## 3. EventBus 调度模型

### 3.1 当前问题是否存在

**存在，但原方案未经证明。** `publish()` 对每个匹配 Handler 无界创建 task；
EventBus 保存强引用并能正常排空，所以问题是运行期容量无上限，不是 task 丢失。

### 3.2 当前真实语义

- 每个 Event × Handler 形成一个 asyncio task；
- `publish()` 调度完成即返回，不等待 Handler；
- 同一 Handler 可重入并发；
- Handler 异常只记录，不传播给 publisher；
- Filter 在 callback task 内执行；
- 不保证事件顺序；
- 慢 Handler 不阻塞其他 Handler，但可累积无界 task；
- `close()` 正常情况下停止接收、限时排空、取消超时任务。

### 3.3 方案比较

| 方案 | 能否限制 task 数 | 语义/成本 | 结论 |
| --- | --- | --- | --- |
| task 内 Semaphore | 否，只限制活跃协程 | pending task 仍无界 | 不足 |
| publish 前容量 Semaphore | 是 | 对 publisher 产生背压，改动最小 | 首选试验 |
| bounded Queue + 固定 worker | 是 | 改变调度、公平性、关闭和异常模型 | 暂不采用 |
| 每订阅者独立 Queue | 是 | 隔离慢 Handler，但状态和 worker 很多 | 有证据后再做 |
| 分层调度器 | 是 | 复杂度最高 | Reject 当前阶段 |
| 保持现状只加指标 | 否 | 只能观测不能保护 | 仅作为第一步 |

### 3.4 推荐语义

第一阶段增加可选 `max_pending_callbacks`，在创建 task 前获取容量，task done 时释放。
容量满时默认 `await`，让 `publish()` 背压；不能静默 drop。未来若有实时、可丢弃
事件需求，可显式增加 `overflow="drop_newest"|"raise"`，但不得作为默认。

一个 Event 匹配多个 Handler 时仍保持一 Handler 一 task。无需先引入
`HandlerJob/ExecutionTask`；只有 queue、重试、优先级或持久化需求出现时才有价值。

Filter 为兼容当前时机和异常边界，先保留在 task 内。若要在入容量前过滤，应另行
评估 Filter CPU 成本、异常行为和同步阻塞，不随容量变更一起修改。

### 3.5 关闭、兼容和回滚

- 先修复 close 自身被取消后的可重试清理；
- 停止接收后等待所有已取得容量的 task；
- 超时取消并 await；
- 默认 `max_pending_callbacks=None` 保持 3.x 行为；
- 通过配置启用有限容量并收集数据；
- 有限默认值属于明显行为变化，应放在明确版本边界；
- 回滚只需恢复 `None`，不迁移持久数据。

### 3.6 推荐任务拆分

#### EVT-01：EventBus 负载与语义基线

- **目标：** 固定 fan-out、pending、延迟、内存和关闭时间基线。
- **非目标：** 实现生产 worker runtime。
- **依赖：** 无。
- **验收：** 可重复测试慢 Handler、突发发布、多 Handler、公平性和关闭。
- **优先级：** P0，Proceed Now。

#### EVT-02：可选容量和背压

- **目标：** 限制 in-flight callback task。
- **依赖：** EVT-01、取消安全修复。
- **API：** EventBus/BotApp 可选容量配置、pending/等待指标。
- **验收：** pending 不超过容量；默认不丢事件；慢 Handler 不导致悬挂关闭。
- **回滚：** 配置为 unlimited。
- **优先级：** P1。

#### EVT-03：固定 worker pool + queue

- **结论：** 当前 Reject。只有 EVT-01 证明 task 调度开销是瓶颈，且明确接受顺序、
  公平性和异常语义变化后再重新设计。

## 4. 配置与 CLI

### 4.1 当前问题

部署入口缺失是真实问题，但环境变量映射和 CLI 是两个独立能力。RuntimeConfig 的
任意对象结构不能靠简单 `os.environ` 扫描安全覆盖；必须先定义 raw 配置合并，再
调用 builder。

### 4.2 配置来源规范

推荐固定优先级：

```text
CLI 显式覆盖 > 环境变量 > YAML > builder/default
```

环境变量读取必须显式触发，例如 `RuntimeConfig.from_sources(...)` 或
`RuntimeConfig.from_yaml(..., env_prefix="BUTTERBOT__")`，不能让
`RuntimeConfig()` 或现有 `from_yaml()` 隐式读取全局环境。

环境变量命名建议使用双下划线分层：

```text
BUTTERBOT__NAPCAT__URL
BUTTERBOT__NAPCAT__TOKEN
```

合并应在原始 dict 层深度覆盖，然后每个顶层 builder 只执行一次。空字符串、
缺失值、布尔/数字解析和未知键必须有确定规则并测试。

secret 要求：

- `NapcatConfig.token` 使用 `field(repr=False)` 或统一 secret wrapper；
- 配置错误不得输出原始 token/cookie；
- 日志只输出配置来源和键名；
- Bilibili Credential 的第三方 repr 无法保证时，不记录整个对象。

### 4.3 CLI 入口

CLI 不依赖插件系统，可独立实现。推荐应用工厂：

```text
butterbot run package.module:create_app --factory
```

第一版命令：

- `butterbot run ENTRYPOINT [--factory] [--config PATH]`
- `butterbot check ENTRYPOINT [--factory] [--config PATH]`
- `butterbot --version`

`run` 加载 `BotApp` 对象或无参/接收 config 的工厂并进入现有生命周期；`check`
只加载配置、构造应用并验证 Source 注册，不连接外部服务，除非应用提供显式
preflight hook。不要在 v1 增加 plugin install/list、daemon 管理或远程控制面。

### 4.4 推荐拆分

- **CFG-01 配置来源与 secret 规范：** P1；保持原构造行为，增加显式合并 API。
- **CLI-01 应用工厂与最小 CLI：** P1；依赖 CFG-01，不依赖 Plugin。
- **结论：** **Split/Proceed in milestone 1**。

## 5. 可观测性

### 5.1 当前问题

NapCat/WebSocket 已有局部 metrics；Bilibili 只有日志；Event 只有 id；所有组件有
状态但无 health 协议。因此“增加 metrics、healthcheck、trace_id”混合了三套不同
数据模型，必须拆分。

### 5.2 所属边界

- core：定义轻量 `HealthSnapshot`、`MetricsSnapshot`/只读采集 Protocol 和
  EventBus 自身指标；
- Source/API：报告领域状态和计数；
- app/部署适配器：聚合 liveness/readiness，并选择日志、Prometheus 或 HTTP 暴露；
- 不创建独立 metrics 服务。

NapCat 与 Bilibili 应实现统一只读接口，但字段允许组件专属扩展。不能强迫轮询
Source 伪装成 WebSocket 连接指标。

### 5.3 Event metadata

建议在 Event 尾部增加可选 metadata，而不是只加 `trace_id`：

- `correlation_id`
- `causation_id`
- 不透明 `attributes` 或受控 metadata 类型

`trace_id` 只在有追踪 provider 时映射/注入。当前不引入完整 OpenTelemetry。

### 5.4 必要指标

EventBus 容量启用后至少提供：

- pending callbacks、capacity；
- publish 数、matched callbacks 数；
- capacity wait 次数/时长；
- Handler 成功、失败、取消；
- Handler 执行时长；
- close 时排空和强制取消数量。

Source health 至少提供 running、last_success、last_error、consecutive_failures。
轮询 Source 还需要 last_poll；WebSocket 需要 connection state、reconnect count。

### 5.5 推荐拆分

- **OBS-01 Event metadata 与日志上下文：P1**
- **OBS-02 进程内 health 契约和聚合：P1**
- **OBS-03 metrics 统一快照及 EventBus 指标：P1，依赖 EVT-02**
- **OBS-04 OpenTelemetry adapter：P3 Defer**

最终结论：**Split**。不能把四项作为一个“低风险”任务。

## 6. Pydantic 私有 API

### 6.1 问题和证据

问题明确存在且只有一个 import 位置：

```text
butterbot/core/data/base_model.py:4
```

私有 ModelMetaclass 用于类创建时 registry 初始化和 discriminator 自动注册。
NapCat 多层消息/通知/请求/元事件与 segment 数据大量依赖它。

### 6.2 替代方案

| 方案 | 兼容性 | 结论 |
| --- | --- | --- |
| 普通 `__init_subclass__` | Pydantic 字段初始化时序较早 | 可行但非首选 |
| 显式 registry | 最稳定，但要求所有模型改注册方式 | 长期可选 |
| `__pydantic_init_subclass__` | 保持自动注册，Pydantic 公开 hook | 首选 |
| 官方 discriminated union | schema 强，但不覆盖现有动态多层 API | 不直接替换 |

### 6.3 回归要求

- 单层、多层、间接继承；
- 多 discriminator value；
- root registry 隔离；
- 普通 DTO 不污染全局 registry；
- 未知/缺失 discriminator；
- `from_type(raw=True/False)`；
- `AutoDispatchList`；
- 真实 NapCat event/segment payload；
- Pydantic 最低和最新允许版本。

### 6.4 实施边界

- 不改变 `from_dict()`、`from_type()` 和用户模型声明方式；
- 删除 `MetaDataModel` 私有继承；
- 依赖限制为 `<3`，主版本升级单独处理；
- 回滚为前一实现和依赖 pin，无数据迁移。

最终结论：**Proceed Now，P0，风险中低。**

## 7. Policy 与 RBAC

### 7.1 当前基础是否存在

不存在 RBAC 所需的稳定领域模型：

- 无 user/subject；
- 无 tenant；
- 无 resource/action 命名；
- 无角色存储、继承或管理控制面；
- Source UUID 不是安全主体；
- Handler 和 API 不携带授权上下文。

直接设计 RBAC 必须虚构产品需求，当前需求证据为 1/5。

### 7.2 capability policy

未来插件或外部自动化更可能先需要 capability：

- 可读取哪些 config namespace；
- 可发布哪些事件；
- 可调用哪些 API/action；
- 可注册哪些 Source/Handler；
- 可使用哪些 secret。

检查点应分层：

- 注册阶段：声明并授予插件 capability；
- API/action 调用阶段：真正执行外部副作用前强制检查；
- 路由/Handler 阶段：仅在事件本身涉及敏感数据时使用；
- 不能只在 Handler 执行阶段检查，因为扩展仍可绕过它直接调用 API。

secret 不应作为普通字符串交给 PluginContext；未来由 capability-aware provider 按
namespace 返回。

### 7.3 推迟条件

完整 RBAC 只有在出现多租户控制面，并明确 subject、role、resource、action、
policy storage、审计和管理员工作流后才进入设计。

推荐：

- **POL-01 capability vocabulary：P2 Design Only，依赖扩展草案**
- **POL-02 完整 RBAC：Reject 当前阶段**

## 8. Docker 与 systemd

### 8.1 必要性

部署示例有用户价值，但当前没有标准应用入口。现在编写模板只能硬编码某个 example
或要求用户自行修改命令，无法形成稳定验收。

### 8.2 推荐边界

- 在 CLI/应用工厂完成后提供最小 Dockerfile、Compose 示例和 systemd unit；
- 使用非 root 用户、只读代码、外部挂载配置、环境变量 secret、SIGTERM；
- smoke 验证 SIGTERM 触发 `BotApp.close()`；
- 不引入 Kubernetes operator、独立 worker 镜像或官方基础镜像发布流水线。

最终结论：**Defer，P2**；前置 CFG-01、CLI-01。

## 9. Contract、Load、Release Smoke Test

### 9.1 三者不是同一任务

#### TEST-01：EventBus/load baseline

- **目标：** 决定是否以及如何限流；
- **验收：** 可重复 fan-out、突发、慢 Handler、关闭、内存与尾延迟结果；
- **优先级：** P0。

#### TEST-02：wheel release smoke

- **目标：** 在发布前验证构建产物，而不是源码树；
- **实现：** 干净 venv 安装 wheel，检查版本、公开 import、构造/关闭 BotApp、运行
  不依赖外网的最小示例；
- **前置：** build；
- **回滚：** 移除 CI step；
- **优先级：** P0。

#### TEST-03：extension contract tests

- **目标：** 为外部 Source/API/Data/Type/Filter 提供可复用契约；
- **现状重叠：** 当前 core 单测和扩展测试文档已有部分契约，但没有可安装第三方包
  的独立测试套件；
- **验收：** 生命周期、取消、幂等关闭、配置缺失、事件发布和无遗留 task；
- **优先级：** P1。

最终结论：**Split**。原任务的“低风险”判断低估了 load 语义设计成本。

## 10. 通用 Source

### 10.1 Cron

- **复杂度：** 四者最低；
- **用途：** 最适合验证框架能否超越 Bot 输入，且不需要 Event envelope 扩展；
- **生命周期：** scheduler task 由 Source 创建和停止；触发重叠策略必须显式；
- **重试：** 调度触发与 Handler 失败分离，Source 不自动重试业务 Handler；
- **归属：** 优先独立可选包，避免把 scheduler 依赖加入核心；
- **优先级：** P2，四者第一。

注意：APScheduler 当前仅作为 `bilibili-api-python` 的传递依赖出现，不能把它当作
ButterBot 可稳定使用的直接依赖。

### 10.2 Webhook

- **复杂度：** 中高，需要 HTTP server、bind/port、请求大小、超时、认证、优雅
  关闭和响应语义；
- **架构：** 应拆为通用 ingress（接收、认证、限流、生成 metadata）和 adapter
  （payload → Data/Type）；
- **重试：** 入站 HTTP 不在 Source 内长期重试；返回状态由接收结果决定，业务
  Handler 异步失败不能伪装成 HTTP 同步失败；
- **依赖：** Event metadata、health、部署配置；
- **归属：** 独立包或 optional extra，不进入 core；
- **优先级：** P2，Cron 之后。

### 10.3 GitHub

- **关系：** GitHub webhook 应是通用 Webhook ingress 上的 adapter，不重复维护
  HTTP server；
- **额外边界：** 签名校验、event/delivery id、payload schema、redelivery；
- **Event metadata：** delivery id 映射 correlation/idempotency metadata；
- **归属：** 独立包；
- **优先级：** P3，依赖 Webhook。

### 10.4 Mail

- **复杂度：** 最高，涉及 IMAP IDLE/轮询、连接恢复、游标、重复邮件、附件上限、
  OAuth/密码和服务商差异；
- **重试边界：** 连接重试属于 Source；业务处理重试不属于 Source；
- **归属：** 独立包；
- **优先级：** P3 Defer，必须先有明确用户和服务商范围。

最终结论：**Split**，顺序为 Cron → Webhook ingress → GitHub；Mail 独立延后。

## 11. NcatBot / NoneBot2 桥接器

### 11.1 价值和证据

潜在价值是复用已有适配器或降低迁移成本，但仓库没有用户故事、依赖、兼容测试或
目标版本。ButterBot 已直接提供 NapCat OneBot Source/API，NcatBot 桥接可能与
现有能力重复；NoneBot2 是完整运行时，桥接会涉及双重事件循环、驱动、依赖注入和
关闭所有权。

### 11.2 推荐边界

- 初期只做单向“外部框架事件 → ButterBot Event”适配；
- 动作调用继续使用一个明确的宿主 API，避免双向事件回环；
- 放在独立仓库/distribution；
- core 不 import NcatBot/NoneBot2，使用 optional dependency；
- 兼容矩阵至少包含 ButterBot、目标框架、Python 和协议/adapter 版本；
- 等 provisional 扩展注册入口稳定后再实现。

双向桥接只有在明确需要 ButterBot Handler 驱动外部框架动作、并定义回环检测和
生命周期宿主后才评估。

最终结论：**Defer，P3**。

## 12. 插件生态治理

以下能力不能合并为一个任务：

| 能力 | 技术成本 | 安全成本 | 治理/运营成本 | 结论 |
| --- | --- | --- | --- | --- |
| 兼容声明 | 中 | 低 | 低 | P2，依赖 manifest |
| 自动兼容测试 | 中高 | 低 | 中 | P2，依赖 contract tests |
| curated directory | 中 | 中 | 高 | P3，达到生态阈值后 |
| 完整性校验 | 低中 | 中 | 中 | 优先复用 wheel RECORD/PyPI hash |
| 发布者签名 | 高 | 高 | 高 | Defer，先定义信任目标 |
| 密钥撤销 | 高 | 高 | 很高 | 签名之前不得单独实施 |
| 安全公告 | 低中 | 中 | 高 | 有 curated 插件后建立流程 |
| 插件评分 | 中 | 中 | 很高 | Reject 当前阶段 |

### 12.1 兼容声明与自动测试

第一阶段只需 `requires_butterbot`、Python 版本和 capability/schema version。
自动测试应安装发布 wheel 并运行扩展 contract suite。测试通过代表 API 兼容，不
代表插件安全或业务正确。

### 12.2 目录

curated directory 只有在至少约 10 个维护中的扩展、3 个以上独立发布者、明确收录
和下架责任人后才有收益。否则文档中的人工列表更便宜。

### 12.3 完整性、签名和撤销

wheel RECORD 和包索引 hash 已提供内容完整性基础。自建第二套 hash 没有身份保证。
发布者签名必须同时解决身份验证、密钥保护、轮换、撤销、时间戳和客户端信任根。
在没有分发渠道和运营责任前实施只会制造虚假安全感。

### 12.4 安全公告与评分

安全公告需要报告入口、影响版本、协调披露、撤回/标记机制和维护人员。评分还需要
反刷、争议处理、隐私和内容审核，当前 Reject。

最终结论：**Split**。兼容声明和自动测试进入 P2；目录、安全公告 P3 条件触发；
自建完整性、签名、撤销和评分当前 Reject/Defer。

## 13. 独立重排结论

### P0

1. 修复取消安全和可重试关闭（审查新增）
2. 去除 Pydantic 私有元类并限制主版本
3. EventBus 负载/语义基线
4. 发布前 wheel smoke

### P1

1. EventBus 可选容量和背压
2. 配置来源合并与 secret 脱敏
3. 应用工厂和最小 CLI
4. Event metadata、health、metrics 的分拆实现
5. 外部扩展 contract tests

### P2

1. provisional 扩展契约
2. capability vocabulary 设计
3. Docker/systemd 示例
4. Cron 独立扩展
5. Webhook ingress
6. manifest 兼容声明和自动兼容测试

### P3

1. 稳定插件 API（满足外部验证条件后）
2. GitHub adapter、Mail Source
3. NcatBot/NoneBot2 单向桥接
4. OpenTelemetry adapter
5. curated directory 和安全公告流程

### Reject

- 当前完整 RBAC；
- 未经基线的固定 EventBus worker pool；
- 独立 RouteSpec 路由系统；
- 当前插件评分；
- 把签名描述为 Python 插件沙箱；
- 当前独立 Router/Worker/Policy/Metrics/Registry 服务。
