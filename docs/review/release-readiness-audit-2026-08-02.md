# ButterBot 3.1.0.dev2 发布前最终审查

> 审查日期: 2026-08-02
> 代码基线: `dev_main` / `d6ef240fdbd10e9fb830ff0e362b058f711ea730`
> 审查门槛: 公开 Beta 与 RC, 不按正式稳定版门槛评判
> 文档性质: 发布决策快照. 本文不修改生产代码, 也不代替修复后的重新验收.
>
> 后续状态: 本文记录 `d6ef240` 的初审问题. Beta 阻断修复后的验收结论见
> [3.1.0b1 Beta 发布验收](./beta-release-acceptance-2026-08-02.md).

## 1. 结论

当前 HEAD **不应直接发布为公开 Beta, 更不满足 RC**. 更准确的定位是:

- 核心 Source 开发路径已经达到 **Beta 候选**: 用户可以继承 `BaseSource`, 定义
  `BaseType`/Data, 手动加入 `BotApp`, 发布事件并完成生命周期清理;
- Handler 插件的 distribution entry point 和本地目录两条路径已经达到
  **Beta 候选**: 仓外 wheel 和本地目录 smoke 均通过;
- 公开契约、发布脚本和异常边界尚未完成 Beta 收口, 不能称为稳定插件平台;
- 当前没有证据支持“服务器至少一周无人值守”的承诺, 已知恢复和容量问题也使该
  承诺在默认配置下不成立.

### 1.1 发布判断矩阵

| 审查目标 | 当前判断 | 说明 |
| --- | --- | --- |
| 用户编写自定义事件源 | **Beta 条件通过** | 手动装配路径完整; 自动发现、稳定健康上报契约和独立 adapter wheel 验证仍缺失 |
| 用户编写 Handler 插件 | **Beta 候选, 当前发布阻断** | 外部 wheel/本地目录 smoke 通过; 生命周期取消竞态和稳定性表述尚未收口 |
| 作为公开 Beta 发布 | **NO-GO** | 基础 wheel smoke 当前确定失败, 且仍有两个可复现的异步 P1 |
| 作为 RC 发布 | **NO-GO** | API 尚未冻结, 插件仍标为实验性, 真实上游和耐久验收缺失 |
| 至少一周无人值守 | **未证明且默认配置不满足** | 没有 7 天 soak; 部分断线不自愈, EventBus 默认无界, CLI 后台输出不轮转 |

如果必须立即对外提供版本, 最多只能称为 **developer preview**. 在修复第 7.1 节
的 Beta 阻断项后, 才适合启动有明确限制、允许人工观察和重启的公开 Beta.

## 2. Beta 与 RC 门槛

本文采用以下标准:

- **Beta**: 主要用户路径闭环, 可以让外部用户在真实但受控的环境中验证; 已知风险
  已明确, 但不得保留会让发布流程确定失败、生命周期失控或文档承诺互相矛盾的
  问题.
- **RC**: 计划公开的作者 API 和行为基本冻结, 发布产物、文档、测试和升级边界一致;
  不存在已知发布阻断项, 并有与目标运行时长相称的真实集成和耐久证据.

“Beta/RC”只降低生态成熟度与兼容历史的要求, 不降低资源释放、取消、背压和故障
可见性的要求.

## 3. 可复现验证结果

### 3.1 通过项

| 验证 | 结果 |
| --- | --- |
| 完整测试与覆盖率 | `713 passed`; 总 branch coverage `82.37%` |
| 关键区域独立门禁 | Bilibili `83.96%`; NapCat `86.96%`; WebSocket `87.27%`; CLI runtime `80.36%` |
| Ruff | 通过 |
| Ruff format check | 通过, 183 个文件已格式化 |
| Pyright | 通过, 0 error / 0 warning; 当前仍是 `basic` 模式 |
| VuePress/Markdown/链接 | 构建 50 页, lint 与内部链接检查通过 |
| sdist/wheel 构建 | `3.1.0.dev2` sdist 与 wheel 构建成功 |
| 基础 wheel 安装 | 在干净 Python 3.12 venv 安装成功, 基础依赖没有拉入 adapter 依赖 |
| adapter extras | `napcat`、`bilibili`、`all` 三个隔离安装 smoke 通过 |
| 外部插件 wheel | discovery、Handler 路由、失败回滚、幂等关闭 smoke 通过 |
| 本地目录插件 | 两个不同绝对路径的隔离加载与 Handler 路由 smoke 通过 |
| 最小 Source 示例 | `uv run examples/minimal_source_example.py` 输出 `ready` 并正常关闭 |
| CLI 基础面 | `--version`、主 help、`run` 和 `plugin` help 正常 |

本次只在本地 Python 3.12.3 执行. CI 声明 Python 3.12、3.13、3.14 矩阵, 但远端
运行状态不作为本次本地审查的已通过证据.

### 3.2 确定失败项

隔离安装 dev2 wheel 后执行 [smoke_wheel.py](../../scripts/smoke_wheel.py) 立即失败:

```text
ImportError: cannot import name 'SourceFactoryRegistry' from 'butterbot.app'
```

统一装配改造已经把 `SourceFactoryRegistry` 降为内部实现, 而 smoke 仍从
`butterbot.app` 导入它. [test_package.py](../../tests/test_package.py) 甚至明确断言该
名称不再公开. 因此当前源码测试全绿与发布 smoke 失败并不矛盾: pytest 没有执行这个
脚本, 但 CI 和 release workflow 会执行它.

这是一项确定的发布阻断, 不是仅在真实上游才可能发生的风险.

### 3.3 当前 HEAD 重新复现的异步问题

1. 插件 `on_start` 超时后, `_run_callback()` 只 `cancel()` 而不等待任务静默.
   一次性复现中, 超时返回时 `PluginScope.task_count == 1`. manager 随后可以进入
   `on_stop`, 使启动和停止同时操作插件资源.
2. WebSocket 发送任务取出消息并阻塞期间, 生产者再次填满容量为 1 的发送队列;
   调用一次 `cancel()` 后, 任务卡在 `await self._send_queue.put(message)`, 实测
   `task.done() == False`.

两项都可能把回滚、重连或关闭路径拖住, 不能因为正常路径测试通过而降级为普通文档
问题. 详细历史分析见[上一轮全项目审查](./project-readiness-audit-2026-08-01.md).

### 3.4 审查限制

- 未连接真实 Bilibili、NapCat 或 QQ 账号;
- 未做 24 小时或 7 天 soak;
- 未做大规模吞吐、慢 Handler、内存/文件描述符上限压测;
- 未做安全渗透、恶意插件隔离或依赖漏洞扫描;
- 远端 GitHub Actions 状态未纳入本地证据.

## 4. 事件源适配审查

### 4.1 已经可用的能力

Source 作者可以只依赖公开门面完成基本适配:

- 从 `butterbot.core` 导入 `BaseSource`、`BaseType`、`Event` 和 Data 基类;
- 在 `on_start()`/`on_stop()` 中持有并释放 task、连接或监听器;
- 使用 `self.ctx.bus.publish(self.uuid, event)` 发布事件;
- 通过 `config_key` 和 `ApiRegistry` 复用 API 实例;
- 使用 `source_kind` 让 Handler 插件按逻辑能力路由;
- 由 `BotApp.add_source()` 手动装配, 并由 `SourceManager` 负责回滚和关闭.

[Source 开发指南](../extensions/source.md)、[API 开发指南](../extensions/api.md)、
[扩展测试指南](../extensions/testing.md)和最小示例已经覆盖一条完整路径. Source
生命周期也具备以下可靠性基础:

- 启动、停止串行化;
- 启动失败调用 `on_stop()` 回滚;
- 停止失败保留 cleanup ownership, 后续可以重试;
- manager 动态增删、应用关闭和 EventBus 排空均有回归.

因此, **外部用户现在能够编写并运行自定义 Source**. 这不是只有内部 adapter 才能
使用的代码路径.

### 4.2 必须明确的能力边界

1. **没有自定义 Source 自动发现/自动 YAML 工厂注册**. 内部 factory registry 只
   识别内置 adapter. 第三方 Source 必须由用户应用工厂导入并调用
   `app.add_source()`. 这可以作为 Beta 设计边界, 但不能宣传成“安装 adapter 后仅改
   YAML 即可使用”.
2. **插件不能拥有 Source**. 插件只注册 Handler; 长期外部连接必须由应用 Source
   管理. 当前 Handler 插件文档已经说明该规则.
3. **缺少独立 Source distribution fixture**. 现有外部插件 smoke 在仓库外定义了
   自定义 Source, 能证明公开 import 和手动装配可用, 但没有验证“单独安装第三方
   adapter wheel -> 应用装配 -> 跨版本兼容”的完整发行形态.
4. **Source 健康上报缺少稳定作者 API**. `BaseSource` 自动在启动成功后置为 ready,
   运行期恢复/降级只能调用下划线方法 `_report_ready()` 和
   `_report_degraded()`. 稳定性文档又把下划线名称定义为 internal. RC 前需要公开并
   测试健康上报契约, 或明确健康完全由框架推导.
5. **`supported_types` 定义期检查无效**. `BaseSource` 已定义
   `supported_types=None`, 所以子类继承后 `hasattr()` 永远为真. 遗漏声明会到订阅
   阶段才失败, 与指南中的“必须声明”不一致.

### 4.3 Source 结论

- 作为 **Beta 手动适配 API**: 条件通过;
- 作为 **可自动安装的 adapter 生态**: 尚未完成;
- 作为 **RC 级冻结契约**: 不通过, 需要先解决健康上报和兼容边界.

## 5. 插件编写审查

### 5.1 已经可用的能力

当前插件系统支持:

- distribution `butterbot.plugins` entry point;
- 带 `plugin.toml` 的便携本地目录;
- descriptor、核心版本约束和插件依赖拓扑;
- `@register(source_kind, status)` Handler 声明;
- 不可变私有配置模型;
- `context.spawn()` 和 `context.add_cleanup()` 资源托管;
- Source/API 只读查询;
- 注册失败、Source 启动失败、插件启动失败时的逆序回滚;
- 插件状态和不包含 secret/异常消息的健康摘要.

本次隔离 wheel 和本地目录 smoke 都通过, 所以“用户能否根据当前版本写出可加载的
Handler 插件”的答案是 **能**.

### 5.2 仍不能称为稳定插件 API 的原因

1. [插件指南](../extensions/plugins.md)标题仍是“实验性插件系统”, 扩展入口将其描述
   为 provisional; [插件 API](../api/plugin.md)和包 docstring 又称其为“稳定作者
   API”. [稳定性说明](../api/stability.md)同时写明 `3.1.0.dev2` 尚处于 clean-break
   窗口, stable API 只在未来稳定版发布后开始受 SemVer 保护. 三种表述不能同时作为
   RC 承诺.
2. 插件生命周期超时存在已复现的启动/停止重叠风险. 对可信插件也必须保证框架不会
   主动制造并发生命周期.
3. `PluginScope._close()` 超时后可以继续执行 cleanup, 而拒绝取消的后台 task 仍可能
   存活; 当前没有隔离或下一代实例禁止策略的公开语义.
4. `PluginContext.get_source()`/`get_sources()` 的返回类型是 `object`, 插件作者无法
   从类型系统得到 Source 能力. Beta 可以用显式 cast, RC 应决定是否提供泛型或稳定
   协议.
5. 示例插件依赖写作 `butterbot-python>=3.1.0.dev2,<4`, 但稳定性文档又声明当前
   dev 窗口可以 clean break. 在首个稳定契约前, 该范围对未来 dev 版本给出了过强的
   兼容暗示.
6. 插件拥有当前 Python 进程的完整权限. 文档已经正确说明它不是沙箱; 发布说明必须
   保留“仅加载可信插件”的边界.

### 5.3 插件结论

- 作为 **可信 Handler 插件的受控 Beta**: 代码路径成立, 修复生命周期 P1 后可发布;
- 作为 **稳定/RC 插件平台**: 不通过;
- Source provider 插件不是当前能力, 不应作为缺陷误报, 但必须在发布说明中说清楚.

## 6. 至少一周无人值守审查

### 6.1 已有的长期运行基础

- `BotApp.run()` 在 CLI 模式处理 `SIGINT`/`SIGTERM`, 并进入完整关闭路径;
- Source、EventBus、API 和插件资源都有明确所有权; EventBus 与插件清理有阶段预算,
  Source/API 采用可重试或尽力关闭;
- managed file log 使用 UTC 午夜轮转, 默认保留 7 份;
- CLI 每秒原子更新本地健康摘要, `status` 能识别 degraded 和超过 5 秒的陈旧报告;
- NapCat WebSocket 有指数退避、抖动、健康状态、有界发送队列和有界 listener;
- `reconnect_attempts=0` 支持无限重连;
- 运行状态不会持久化配置内容、环境变量或异常消息.

这些能力说明项目已经从“只能跑通示例”进入“可以开展长稳验证”的阶段.

### 6.2 阻止一周承诺的已知问题

#### 6.2.1 没有耐久证据

仓库没有 24 小时或 7 天测试结果, 也没有 RSS、task、thread、文件描述符、aiohttp
session、callback、listener、发送队列和 pending request 的时间序列. 单元测试十秒内
完成不能外推为运行一周.

#### 6.2.2 EventBus 默认无界

`EventBus(max_pending_callbacks=None)` 和 `BotApp` 的默认值都是无界. 每个匹配
Handler 会创建一个 task; 生产速率长期高于消费速率时, task 和内存可以持续增长.
虽然应用工厂能显式设置上限, YAML/CLI 没有提供该生产安全值, 快速开始也使用默认值.

#### 6.2.3 连接和后台任务不具备统一自愈

- Bilibili danmaku worker 运行期断线后会报告 degraded 并退出, 但不会自动创建新的
  worker/连接;
- Bilibili polling 对单目标异常只记录日志并继续, 没有调用 Source degraded 健康
  上报. 持续请求失败时 `status` 仍可能显示 ready;
- NapCat 默认只重连 5 次, 用尽后保持 degraded/stopped; 只有显式配置 `0` 才无限
  重试;
- 插件后台 task 失败会进入诊断, 但框架不会监督并重启该 task;
- 应用进程本身没有 supervisor. CLI `restart` 是命令, 不是自动恢复策略.

因此, 即使进程 PID 仍存活, 关键事件能力也可能已经停止. 只配置 systemd
`Restart=on-failure` 不能处理“进程存活但 Source 已降级”的情况.

#### 6.2.4 日志和告警仍不足

managed `logs/bot.log` 会轮转, 但 `butterbot run --background` 追加写入的
`.butterbot/butterbot.log` 不轮转. 高日志量运行一周可能持续占用磁盘.

CLI 状态文件提供拉取式健康信息, 但没有内置告警、健康 HTTP endpoint 或根据降级
自动退出/重启的策略. 这可以交给外部运维系统, 但仓库当前没有给出完整部署模板和
健康检查策略.

#### 6.2.5 已知取消问题会影响恢复和关闭

WebSocket 满队列取消问题可能拖住重连主循环或 shutdown. 插件生命周期取消问题会
让失败回滚与清理并发. 两者都与长时间运行中必然发生的断线、超时和部署重启直接
相关.

### 6.3 一周无人值守结论

当前答案是 **不能承诺**. 对低流量、无 Bilibili danmaku、显式设置 EventBus 上限、
NapCat 无限重连并由外部监控轮询 `butterbot status` 的受控部署, 有可能连续运行一周;
但这是有条件的试运行方案, 不是当前默认配置已经证明的产品能力.

## 7. 发布阻断项与验收顺序

### 7.1 公开 Beta 前必须完成

| ID | 阻断项 | 完成判据 |
| --- | --- | --- |
| B-01 | 基础 wheel smoke 使用已删除的公开导出 | 干净 venv 中 `scripts/smoke_wheel.py` 通过, 且只使用最终公开 API |
| B-02 | WebSocket 满队列取消可悬挂 | 单次取消在固定预算内结束; 重连、重放/丢弃和 echo 语义有回归 |
| B-03 | 插件回调超时后未等待静默 | 明确保证 `on_start` 退出后才调用 `on_stop`, 或隔离失败实例且跳过并发 stop |
| B-04 | 插件稳定性承诺互相冲突 | 明确统一为 Beta/provisional, 或完成冻结后统一为 stable; 文档、docstring、版本要求一致 |
| B-05 | PyPI README 尾部包含三行内部规划文字 | 删除内部便笺; 构建后的 METADATA/项目页只包含用户文档 |

如果实际版本号要使用 `3.1.0bN` 或 `3.1.0rcN`, 还必须修改
[release-on-version.yml](../../.github/workflows/release-on-version.yml). 当前校验只接受
`x.y.z.devN` 和正式 `x.y.z`, 会拒绝 Beta/RC 版本. 如果继续发布 `.dev2`, 这一项不
阻断, 但版本名称也不能对外称为 RC.

### 7.2 RC 前必须完成

1. 完成全部 Beta 阻断项;
2. 冻结并统一 Source/插件作者 API 稳定性边界;
3. 给 Source 作者提供受支持的运行期 ready/degraded 上报语义;
4. 增加独立第三方 Source wheel fixture, 验证只使用公开 API 的安装与装配;
5. 为生产入口设置有界 EventBus 默认值, 或提供显式且强提示的生产配置;
6. 为 Bilibili danmaku 增加自动恢复, 为 polling 失败建立正确健康状态;
7. 处理 CLI 后台输出轮转, 提供外部 supervisor 与健康检查部署说明;
8. 完成真实 NapCat/Bilibili 联调和故障注入;
9. 至少完成 24 小时 soak 后再冻结 RC. 如果发布说明要承诺“一周无人值守”, 必须
   在候选提交上完成实际 7 天验收, 不能用 24 小时替代;
10. 检查一周内 RSS、task、thread、FD、session 和各队列没有持续线性增长, 断网、
    服务端重启、限流、慢 Handler、插件 task 失败和 SIGTERM 后状态与资源均符合预期.

### 7.3 不阻断 Beta, 但应列入发布说明

- 第三方 Source 只能由应用工厂手动装配, 不能安装后自动写入 YAML;
- 插件是可信进程内代码, 不是隔离沙箱;
- 插件只拥有 Handler 和自身资源, 不拥有 Source;
- `cli_mode=False` 是嵌入宿主语义, 默认不接管信号; 宿主必须持有 event loop、日志
  和停止事件;
- 当前没有热重载、远程控制面或多实例 supervisor;
- 本轮没有安全渗透和依赖漏洞扫描证据.

## 8. 建议发布路径

### 阶段 A: 修复当前发布阻断

按 B-01 -> B-02 -> B-03 -> B-04/B-05 的顺序分别提交, 每个异步修复同时加入回归.
之后重新执行 release workflow 的全部本地等价命令.

### 阶段 B: 有限公开 Beta

Beta 发布说明应明确:

- 只承诺受控环境验证, 不承诺无人值守生产;
- 自定义 Source 使用应用工厂手动装配;
- 插件仅支持可信 Handler 扩展;
- 推荐显式配置 `max_pending_callbacks`;
- NapCat 长期运行建议显式评估 `reconnect_attempts=0`;
- Bilibili danmaku 断线需要外部健康监控和人工/进程级恢复.

Beta 期间收集真实第三方 Source 和插件反馈, 避免仅凭仓库内 fixture 冻结 API.

### 阶段 C: RC

在作者 API 冻结、真实上游联调、恢复策略和耐久验收都通过后再切 RC. RC 提交之后只
接受发布阻断修复, 不再进行插件公开面、Source 装配或生命周期语义重构.

## 9. 最终回答

1. **发布后用户能否适配事件源?** 能, 但当前是手动装配的 Beta 能力, 不是安装即
   自动发现的稳定 adapter 平台.
2. **用户能否编写插件?** 能编写并加载可信 Handler 插件, 外部 wheel 和本地目录路径
   已验证; 但生命周期竞态和稳定性承诺未解决, 不能称为稳定插件 API.
3. **当前是否稳定可用?** 核心正常路径可用, 整体达到 Beta 候选而非 RC; 当前 HEAD
   还有确定的发布 smoke 失败, 所以尚不能直接发布公开 Beta.
4. **能否服务器至少一周无人值守?** 不能据当前证据承诺, 默认配置和部分内置 Source
   也存在明确的容量、自愈与日志风险.

结论保持为: **先修复 Beta 阻断项, 发布有限 Beta 收集真实生态反馈; 完成长稳和
故障恢复验收后再进入 RC.**
