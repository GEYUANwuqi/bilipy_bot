# ButterBot 推荐 Backlog

> 本文中的每个“任务”均可直接转换为独立 Issue。P3 条件任务只有在进入条件满足时
> 才应创建里程碑；Reject 项不建议创建实现 Issue。

## 当前状态

截至 2026-07-27，Issue 1-7 对应的首批工作已完成，其中 Issue 6 是可重复合成
基线，Issue 7 保持默认 unlimited 的兼容策略。Issue 8 及以后尚未开始。关闭这些
Issue 前仍应以本分支完整 CI 和代码评审结果为准。

## 1. 修复 EventBus 关闭取消后的不可重试清理

- **标题：** `fix(core): 修复 EventBus 关闭取消后的悬挂回调`
- **背景：** `EventBus.close()` 在等待 callback 前设置 `_closed=True`。close task
  被取消后再次 close 会直接返回，本次已复现 pending callback 残留。
- **目标：** 关闭过程可重入/可重试；无论等待被取消还是超时，最终都能回收 Handler
  task，并在清理后传播取消。
- **非目标：** 不引入 Queue、worker pool、重试或持久化。
- **实现建议：** 分离“停止接收”和“清理完成”状态；用内部 close task/锁保证并发
  close 共享同一清理；外部调用被取消时保护实际 cleanup，并在 cleanup 完成后重抛。
- **前置任务：** 无。
- **验收标准：** close 等待期被取消后再次 close 的 pending 为 0；并发 close、
  callback 内 close、超时和关闭后 publish 语义保持。
- **测试清单：** 先加回归；取消前/中/后；两个并发 close；Handler 吞/重抛取消；
  无 unfinished asyncio task。
- **文档清单：** 更新 lifecycle、concurrency、EventBus API 的取消语义。
- **风险：** shield 使用不当可能推迟调用者取消；并发 close 可能死锁。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x。
- **独立 PR：** 是，测试和修复可拆为相邻两个 PR，最终合并前一起验证。

## 2. 补齐 SourceManager 启动和动态移除的取消回滚

- **标题：** `fix(app): 完善 SourceManager 取消时的回滚和退订`
- **背景：** `start()` 只捕获 `Exception`，启动取消不会停止此前已启动 Source；
  `remove_source()` 取消时会跳过退订和摘除。
- **目标：** 取消仍触发必要的回滚/摘除，完成清理后传播原始 `CancelledError`。
- **非目标：** 不并行启动 Source，不改变普通异常聚合格式。
- **实现建议：** 对取消建立单独分支；启动取消时逆序停止 `started`；动态移除使用
  finally 完成 `remove_subscribers()` 和 pop；记录清理异常但不覆盖原始取消。
- **前置任务：** 无，可与 EventBus 修复并行。
- **验收标准：** 启动第二个 Source 被取消后第一个已停止；移除取消后 Source 和
  订阅均不存在；manager 状态一致。
- **测试清单：** 启动取消、回滚 stop 失败、remove stop 取消、重复移除、动态源。
- **文档清单：** 更新 SourceManager 取消和动态移除说明。
- **风险：** 取消传播与清理异常优先级处理错误。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x。
- **独立 PR：** 是。

## 3. 让 BotApp 和 ApiRegistry 执行完整 best-effort 关闭

- **标题：** `fix(app): 保证关闭链继续释放 EventBus 和全部 API`
- **背景：** bus 关闭失败/取消会阻止 API 关闭；一个 API 的取消会中止剩余 API，
  而 registry 已先清空。
- **目标：** manager、bus、每个 API 都获得一次关闭机会，最后按确定规则传播取消
  或报告异常。
- **非目标：** 不新增全局异常聚合框架，不自动重试外部网络关闭。
- **实现建议：** 使用嵌套 finally 或小型 best-effort helper；分别捕获
  `CancelledError`；保留首个取消，在所有资源处理后传播；API 清理保留可诊断信息。
- **前置任务：** Issue 1 的 EventBus 关闭语义。
- **验收标准：** manager/bus/API 任一步抛普通异常或取消时，后续资源仍关闭；
  `aclose_all()` 重复调用安全。
- **测试清单：** bus 取消、多个 API 中首个/中间取消、普通异常与取消组合、幂等。
- **文档清单：** 更新 BotApp 和 BaseApi 生命周期契约。
- **风险：** 多异常报告不清晰；误吞取消。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x。
- **独立 PR：** 是。

## 4. 用 Pydantic 公开 hook 替换私有 ModelMetaclass

- **标题：** `refactor(core): 移除对 Pydantic 私有元类的依赖`
- **背景：** `base_model.py` 直接 import `pydantic._internal`，项目又没有 Pydantic
  主版本上界。
- **目标：** 使用公开 `__pydantic_init_subclass__` 保持现有自动 registry 和多层
  discriminator 行为。
- **非目标：** 不改用全量 discriminated union，不改变用户模型声明和序列化。
- **实现建议：** 将注册逻辑移入 BaseDataModel 的公开 hook；保留最近 root 查找、
  多值注册和 root registry 隔离；依赖设置 `<3`。
- **前置任务：** 先扩充分发回归测试。
- **验收标准：** 无 `pydantic._internal` 搜索结果；现有公开 API 和真实 NapCat
  payload 行为不变。
- **测试清单：** 单层、多层、间接继承、多值、重复值、root 隔离、普通 DTO、
  AutoDispatchList、NapCat event/segment、最低/最新允许 Pydantic。
- **文档清单：** 数据模型扩展指南和依赖兼容说明。
- **风险：** 类初始化时序、forward refs、重复注册覆盖。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x。
- **独立 PR：** 是。

## 5. 在发布前增加 wheel 安装 smoke

- **标题：** `ci(release): 发布前验证构建 wheel`
- **背景：** release workflow 构建后直接发布，现有测试从源码树运行。
- **目标：** 在 PyPI publish 前验证 wheel 可安装、导入、报告版本并完成最小生命周期。
- **非目标：** 不连接 NapCat/Bilibili，不测试所有 Python 版本的 wheel。
- **实现建议：** 临时 venv 安装 `dist/*.whl`；从仓库外目录运行 import、BotApp
  构造/close 和打包后的最小 smoke；验证 wheel 中必要包。
- **前置任务：** `uv build`。
- **验收标准：** smoke 位于 publish step 之前；失败阻止发布；不从源码树 import。
- **测试清单：** 版本、公开入口、RuntimeConfig、EventBus、BotApp close。
- **文档清单：** 发布流程和本地复现命令。
- **风险：** 工作目录污染造成假阳性；依赖网络波动。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x。
- **独立 PR：** 是。

## 6. 建立 EventBus 负载和语义基线

- **标题：** `test(event): 建立 EventBus 并发与内存基线`
- **背景：** 已确认 pending task 无上限，但没有真实容量、延迟和公平性数据。
- **目标：** 为容量模型提供可重复证据，并防止调度语义无意变化。
- **非目标：** 不在本任务实现 worker/queue/semaphore；不宣称生产 benchmark。
- **实现建议：** 新建明确标记的 benchmark/load 测试，覆盖 burst、fan-out、慢
  Handler、不同 Handler、公平性、异常、Filter 和关闭。
- **前置任务：** 最好先完成 EventBus 取消安全。
- **验收标准：** 输出发布吞吐、pending 峰值、内存、p50/p95/p99、关闭时间；
  环境噪声大的指标不设脆弱 CI 绝对阈值。
- **测试清单：** 1/10/100 Handler，快慢混合，1k/10k burst，异常和取消。
- **文档清单：** 基准方法、硬件/版本、不能外推的限制。
- **风险：** 微基准误导生产决策；CI 波动。
- **推荐优先级：** P0。
- **推荐版本：** 3.1.x 研究结果，3.2 前完成。
- **独立 PR：** 是。

## 7. 为 EventBus 增加可选 callback 容量和背压

- **标题：** `feat(event): 增加可配置回调容量和发布背压`
- **背景：** 无界 task 可导致运行期资源增长；固定 worker pool 又会过度改变语义。
- **目标：** 在保留一 Handler 一 task 的前提下限制 in-flight task。
- **非目标：** 不实现持久队列、优先级、重试、exactly-once 或独立 worker 服务。
- **实现建议：** task 创建前获取容量，done callback 释放；容量满默认 await；
  `None` 保持 unlimited；Filter 暂留 callback 内。
- **前置任务：** Issues 1、6。
- **验收标准：** pending 不超过配置值；默认不丢 Event；unlimited 模式通过全部
  现有测试；关闭能处理等待容量的 publisher。
- **测试清单：** 容量 1/N、取消等待 publisher、慢/快 Handler、关闭、异常释放、
  无容量泄漏。
- **文档清单：** 背压语义、容量选择、兼容与回滚。
- **风险：** Source 生产循环被背压；全局容量可能产生跨 Handler 干扰。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 8. 定义显式配置来源合并和 secret 脱敏

- **标题：** `feat(config): 增加 YAML/环境变量/覆盖项合并`
- **背景：** RuntimeConfig 只有 Python/YAML；部署需要 env，Napcat token repr 可见。
- **目标：** 提供显式配置来源 API和固定优先级：CLI > env > YAML > default。
- **非目标：** 不自动扫描所有环境变量，不引入远程 secret manager。
- **实现建议：** raw dict 深度合并后执行 builder；使用
  `BUTTERBOT__SECTION__KEY`；secret 字段 `repr=False`；错误只报告键和来源。
- **前置任务：** 无。
- **验收标准：** 旧 API 行为不变；env 必须显式开启；类型转换和未知键行为确定；
  secret 不进入 repr/日志/异常。
- **测试清单：** 优先级、嵌套覆盖、空值、bool/int/float、非法值、自定义 builder、
  secret 泄漏。
- **文档清单：** 来源优先级、命名、secret、安全示例、迁移。
- **风险：** 通用类型推断歧义；第三方配置对象 repr 不受控。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 9. 增加应用工厂和最小 butterbot CLI

- **标题：** `feat(cli): 增加应用工厂运行入口`
- **背景：** 包没有 console script，部署模板无法稳定发现用户应用。
- **目标：** 支持 `butterbot run module:create_app --factory`、`check` 和
  `--version`。
- **非目标：** 不实现插件安装、daemon、远程控制面或项目脚手架。
- **实现建议：** 标准库 argparse 足以满足 v1；entrypoint 支持 BotApp 对象和工厂；
  使用现有 `BotApp.run()`/异步生命周期；明确 import/类型/配置错误。
- **前置任务：** Issue 8。
- **验收标准：** wheel 安装后 console script 可用；SIGINT/SIGTERM 正常关闭；
  `check` 默认不连接外部服务。
- **测试清单：** 对象/工厂、缺失模块/属性、错误返回码、信号、版本、配置路径。
- **文档清单：** CLI reference、应用工厂示例、部署错误排查。
- **风险：** 工厂签名过早固化；跨平台信号差异。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 10. 增加 Event correlation/causation metadata

- **标题：** `feat(event): 增加可选事件关联元数据`
- **背景：** Event 只有 id，无法关联 webhook、派生事件和 API 动作日志。
- **目标：** 区分 event id、correlation id、causation id，并提供日志上下文传播。
- **非目标：** 不把 trace_id 等同 correlation，不强制 OpenTelemetry。
- **实现建议：** 在 dataclass 尾部增加有默认值的轻量 metadata；Source 可从外部
  delivery/request id 填充；派生事件复制 correlation、设置 parent causation。
- **前置任务：** 无，可与配置并行。
- **验收标准：** 旧位置参数构造兼容；repr 不泄露任意敏感 attributes；日志可带
  event/correlation。
- **测试清单：** 默认值、显式值、派生传播、序列化/repr、旧构造。
- **文档清单：** 四类标识定义和 Source 作者指南。
- **风险：** metadata 变成无约束杂物箱；PII 进入日志。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 11. 定义统一进程内 health snapshot

- **标题：** `feat(observability): 增加应用和 Source 健康状态聚合`
- **背景：** 现有 running/closed/WebSocketState 分散，无法统一 readiness。
- **目标：** 定义 live、ready、degraded、unhealthy 和组件详情。
- **非目标：** 不在 core 启动 HTTP server，不绑定 Kubernetes。
- **实现建议：** core 定义不可变 snapshot/Protocol；Source/API 可选实现；app 聚合
  required/optional 组件；部署 adapter 决定如何暴露。
- **前置任务：** 生命周期状态修复。
- **验收标准：** NapCat、Bilibili polling、EventBus 有合理映射；关闭应用不 ready；
  局部可选失败为 degraded。
- **测试清单：** 各状态转换、最后错误/成功时间、聚合、关闭、未实现组件。
- **文档清单：** 状态定义、部署映射、不得以 liveness 代替 readiness。
- **风险：** readiness 定义与用户部署不一致。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 12. 统一 metrics snapshot 并补 EventBus 指标

- **标题：** `feat(observability): 统一运行指标快照`
- **背景：** WebSocket/NapCat 已有 dict metrics，Bilibili 和 EventBus 指标不足。
- **目标：** 提供依赖无关的只读 metrics 接口和稳定指标命名。
- **非目标：** 不直接依赖 Prometheus/OpenTelemetry，不启动独立 metrics 服务。
- **实现建议：** 定义 snapshot/collector Protocol；适配现有 WebSocket 字典；
  EventBus 增加 publish、matched、pending、wait、成功/失败/取消、执行时长。
- **前置任务：** Issue 7；health 可并行。
- **验收标准：** 指标读取无副作用；标签基数受控；NapCat/Bilibili 实现统一入口。
- **测试清单：** 计数准确、异常/取消、容量等待、快照隔离、并发读取。
- **文档清单：** 指标名、单位、生命周期、Exporter 示例。
- **风险：** 高基数 source/event 标签；指标命名过早稳定。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 13. 发布可复用的外部扩展 contract tests

- **标题：** `test(extension): 提供第三方扩展契约测试套件`
- **背景：** core 单测完整，但外部包无法复用统一生命周期和关闭验证。
- **目标：** 验证 Source/API/Data/Type/Filter 的最低兼容契约。
- **非目标：** 不保证第三方业务正确，不做安全扫描。
- **实现建议：** 提供 pytest helpers/fixtures；用独立样例 distribution 在干净环境
  安装；覆盖配置、事件、取消、超时和幂等关闭。
- **前置任务：** Issues 1-4 稳定后。
- **验收标准：** 样例外部包不 import 私有成员；最低支持版本和当前版本均通过。
- **测试清单：** Source start/stop、API aclose、事件匹配、过滤、错误、无遗留 task。
- **文档清单：** 扩展作者运行方法和兼容含义。
- **风险：** 测试 helper 自身变成未声明公共 API。
- **推荐优先级：** P1。
- **推荐版本：** 3.2。
- **独立 PR：** 是。

## 14. 试验 provisional extension discovery

- **标题：** `feat(extension): 试验 Python entry point 扩展发现`
- **背景：** 当前扩展可手动组合，但没有 distribution 发现和兼容声明。
- **目标：** 发现一个 distribution 提供的一组 Source/API/Handler/ingress 能力。
- **非目标：** 不稳定发布 Plugin API，不实现市场、安装器、签名或沙箱。
- **实现建议：** 最小 manifest 含 schema/id/version/requires/entrypoint/capabilities；
  注册函数复用现有 BotApp/AppContext；放 provisional 命名空间。
- **前置任务：** Issues 8、13；至少一个外部原型。
- **验收标准：** 三类外部样例可发现、注册、失败隔离、关闭；不创建重复 Router。
- **测试清单：** 无 entrypoint、版本不兼容、重复 id、注册失败、卸载/关闭、wheel。
- **文档清单：** provisional 警告、信任模型、生命周期、manifest schema。
- **风险：** 过早固化；同进程代码被误认为受限。
- **推荐优先级：** P2。
- **推荐版本：** 3.3+ experimental。
- **独立 PR：** 是。

## 15. 定义扩展 capability vocabulary

- **标题：** `design(extension): 定义扩展能力声明和受限上下文边界`
- **背景：** 完整 RBAC 缺少领域基础，但未来扩展可能需要限制 config/API/secret。
- **目标：** 定义可注册 Source/Handler、可读配置、可调用 API/action 等 capability。
- **非目标：** 不实现 tenant/user/role，不声称同进程安全隔离。
- **实现建议：** 先设计 vocabulary 和审计点；只有实际 enforcement 需求出现时提供
  包装 AppContext 的窄化 PluginContext。
- **前置任务：** Issue 14 的外部原型。
- **验收标准：** 至少两个扩展用例验证；API/action 检查不能被普通注册路径绕过；
  文档明确可信代码限制。
- **测试清单：** capability 缺失、最小授权、secret namespace、API 拒绝、审计。
- **文档清单：** 威胁模型、非目标、检查点。
- **风险：** facade 被误认为沙箱；能力粒度不稳定。
- **推荐优先级：** P2 Design Only。
- **推荐版本：** 3.3+ experimental。
- **独立 PR：** 是，设计和 enforcement 必须分 PR。

## 16. 增加 CLI 驱动的 Docker 和 systemd 示例

- **标题：** `docs(deploy): 增加 Docker 和 systemd 部署模板`
- **背景：** 当前没有标准部署示例，直接编写会缺少稳定应用入口。
- **目标：** 展示非 root、配置注入、日志、SIGTERM 和重启策略。
- **非目标：** 不实现 Kubernetes operator、官方镜像流水线或多 worker。
- **实现建议：** 模板调用 `butterbot run ... --factory`；配置只读挂载或 env；
  systemd 使用 `ExecStart`、`EnvironmentFile`、合理 `TimeoutStopSec`。
- **前置任务：** Issues 8、9。
- **验收标准：** Docker/systemd smoke 中 SIGTERM 完成 Source→Bus→API 关闭；无 secret
  写入镜像。
- **测试清单：** image build、容器启动/停止、无配置错误、systemd unit verify。
- **文档清单：** 两种部署指南、secret 和日志路径。
- **风险：** 模板维护、基础镜像安全更新。
- **推荐优先级：** P2。
- **推荐版本：** 3.3。
- **独立 PR：** Docker 与 systemd 可各自独立 PR。

## 17. 发布独立 Cron Source 原型

- **标题：** `feat(source): 试验独立 Cron 事件源`
- **背景：** Cron 是验证非 Bot 自动化 runtime 的最小 Source，复杂度低于 Webhook、
  GitHub 和 Mail。
- **目标：** 按计划产生 typed Event，并正确管理 scheduler task。
- **非目标：** 不实现分布式 scheduler、持久 job store 或 exactly-once。
- **实现建议：** 独立 distribution/optional extra；显式 timezone、misfire 和重叠
  策略；Source 只负责触发，不重试业务 Handler。
- **前置任务：** Issue 13；建议有 health snapshot。
- **验收标准：** start/stop 幂等，无遗留 task；取消和时区行为确定；不依赖传递
  APScheduler 版本。
- **测试清单：** 单次/周期、重叠、misfire、取消、异常、关闭、fake clock。
- **文档清单：** 调度语义、非 exactly-once、部署时区。
- **风险：** 时间测试不稳定；传递依赖误用。
- **推荐优先级：** P2。
- **推荐版本：** 独立包 0.x，对应 ButterBot 3.3+。
- **独立 PR：** 是；最好独立仓库。

## 18. 发布通用 Webhook ingress 原型

- **标题：** `feat(source): 试验通用 Webhook ingress`
- **背景：** GitHub 等 HTTP Source 应共享 server 生命周期、认证、限流和 metadata。
- **目标：** 提供 ingress + adapter 结构，把请求转换为 typed Event。
- **非目标：** 不内置所有供应商，不让业务 Handler 结果决定同步 HTTP 成功。
- **实现建议：** 独立包；限制 body/timeout；认证前不解析大 payload；delivery id
  写入 correlation metadata；health 报告 bind/readiness。
- **前置任务：** Issues 8、10、11、13。
- **验收标准：** 优雅启停、认证、大小限制、重复 delivery 策略和背压响应明确；
  GitHub adapter 无需自建 server。
- **测试清单：** 签名/认证失败、超限、慢请求、并发、关闭、adapter 异常、重放。
- **文档清单：** HTTP 语义、反向代理、安全、adapter API。
- **风险：** 暴露网络攻击面；EventBus 背压与 HTTP 状态映射复杂。
- **推荐优先级：** P2。
- **推荐版本：** 独立包 0.x，对应 ButterBot 3.3+。
- **独立 PR：** 是；ingress 与供应商 adapter 分开。

## 19. 条件任务：GitHub、Mail 和框架桥接

- **标题：** `tracking(ecosystem): 收集外部 Source 和桥接器真实需求`
- **背景：** 当前没有用户、目标版本或维护者证据，直接实现会形成长期兼容负担。
- **目标：** 收集 GitHub event 范围、Mail 服务商/认证、NcatBot/NoneBot2 迁移方向。
- **非目标：** 本 Issue 不编写生产桥接代码。
- **实现建议：** 为每个候选记录用户故事、单向/双向、版本矩阵、宿主生命周期和
  维护者；满足条件后拆成独立仓库 Issue。
- **前置任务：** GitHub 依赖 Issue 18；桥接依赖 Issue 14；Mail 无近期前置。
- **验收标准：** 每个进入实现的候选至少有一个真实用户、明确范围和维护负责人。
- **测试清单：** 本跟踪任务无代码测试；实现 Issue 必须定义 contract matrix。
- **文档清单：** 决策记录和不支持范围。
- **风险：** 把“可能有用”误当承诺。
- **推荐优先级：** P3。
- **推荐版本：** 未排期。
- **独立 PR：** 否；后续每个实现必须独立仓库/PR。

## 20. 条件任务：插件兼容和目录治理

- **标题：** `tracking(plugin): 定义插件兼容与治理准入条件`
- **背景：** 兼容声明有技术价值，但目录、签名、撤销、公告和评分需要持续运营。
- **目标：** 先建立 `requires_butterbot` 和自动 contract test；记录生态规模。
- **非目标：** 不当前建设市场、评分、签名服务或密钥基础设施。
- **实现建议：** manifest 试验后增加兼容声明；约 10 个活跃扩展、3 个发布者和明确
  责任人后再提 curated directory；签名前先写威胁模型和撤销方案。
- **前置任务：** Issues 13、14；目录还依赖三个外部扩展的跨版本验证。
- **验收标准：** 自动测试只声明 API 兼容，不宣称安全；所有治理能力有负责人和
  下架/撤销流程。
- **测试清单：** 兼容版本矩阵、安装 wheel、失败报告；治理流程做演练。
- **文档清单：** 兼容含义、信任模型、收录/下架、安全报告。
- **风险：** 虚假安全感、无人维护、评分滥用。
- **推荐优先级：** P2 仅兼容声明；其余 P3/Reject。
- **推荐版本：** 3.3+ experimental；治理未排期。
- **独立 PR：** 兼容声明和自动测试各自独立；目录/签名不得合并。

## 不建议创建的实现 Issue

以下项目在条件变化前保持 Reject：

- 完整 RBAC/PolicyEngine；
- EventBus 固定 worker pool + 全局 Queue；
- 与 Subscriber 平行的 RouteSpec/Router；
- 独立 Plugin Runtime 服务；
- 自建插件完整性系统；
- 发布者签名和密钥撤销基础设施；
- 插件评分系统；
- 双向 NcatBot/NoneBot2 桥接；
- 任何声称安全同进程 Python 沙箱或 exactly-once 的任务。
