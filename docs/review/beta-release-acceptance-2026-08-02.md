# ButterBot 3.1.0b1 Beta 发布验收

> 验收日期: 2026-08-02
> 起始提交: `d6ef240fdbd10e9fb830ff0e362b058f711ea730`
> 验收对象: 起始提交之上的本地 Beta 修复工作区
> 发布范围: 自定义 Source 手动装配、可信 Handler 插件、内置 adapter Beta
> 明确不包含: 第三方 Source 自动发现、RC、正式稳定版和无人值守生产承诺

## 1. 验收结论

当前工作区达到 **有限公开 Beta GO** 标准, 可以作为 `3.1.0b1` 候选提交进入远端
CI 和预发布流程.

| 目标 | 结论 | 边界 |
| --- | --- | --- |
| 自定义事件源适配 | **Beta GO** | 用户应用工厂显式 import 并调用 `BotApp.add_source()` |
| Handler 插件开发 | **Beta GO** | 可信进程内代码; distribution wheel 与本地目录均支持 |
| 基础包与 extras | **Beta GO** | 基础 wheel 不包含 adapter 网络依赖; extras 独立安装 |
| 公开 Beta 发布 | **GO, 待远端 CI** | 本地 release 等价验证通过; 尚未提交、打 tag 或上传 |
| RC | **NO-GO** | 作者 API 尚未冻结, 真实上游和耐久证据仍不足 |
| 一周无人值守 | **不承诺** | EventBus 默认容量、自愈、日志和 7 天 soak 留待后续阶段 |

自动 Source 发现不是本次缺口. 当前正式 Beta 契约就是“框架自动装配内置 Source,
第三方 Source 由应用工厂手动装配”; 文档和项目模板均按该边界表述.

## 2. 初审阻断项关闭情况

| ID | 初审阻断 | 修复与验收 |
| --- | --- | --- |
| B-01 | 基础 wheel smoke 导入内部化的 `SourceFactoryRegistry` | smoke 改为只使用公开 API; 干净基础 wheel 通过 |
| B-02 | WebSocket 满队列取消可能悬挂 | 单一 in-flight slot; 一次取消有界结束; 重连顺序和指标有回归 |
| B-03 | 插件回调超时后可能与 `on_stop` 重叠 | 取消后等待静默; 拒绝取消时跳过并发 stop/cleanup, 后续 close 重试 |
| B-04 | 插件稳定性承诺冲突 | 包、API 和指南统一为 provisional Beta; RC 冻结、正式版 SemVer |
| B-05 | PyPI README 包含内部规划便笺 | 已删除; 构建 wheel 的 METADATA 不再包含这些文字 |
| B-06 | release workflow 不接受 Beta/RC 版本 | 接受 `x.y.zbN`、`x.y.zrcN` 和既有 `.devN`, 均走 prerelease |

## 3. 关键行为变化

### 3.1 WebSocket 发送恢复

消息离开有界发送队列后进入客户端持有的单一 in-flight slot:

```text
queue -> in-flight -> send confirmed -> clear
                   -> disconnect/cancel -> keep -> reconnect retry
                   -> explicit stop -> drop and report
```

取消路径不再执行 `await queue.put()`, 因而不会被已经填满的发送队列反向阻塞.
重连先处理 in-flight, 再处理普通队列. `get_metrics()` 公开以下诊断:

- `send_queue.pending`;
- `send_queue.capacity`;
- `send_queue.inflight`;
- `send_queue.retried`;
- `send_queue.dropped`.

底层连接在“服务端可能已收到, 本地却观察到断线”的边界无法提供 exactly-once,
因此文档明确为 at-least-once. 显式 stop 丢弃当前生命周期未确认的消息.

### 3.2 插件生命周期静默

生命周期回调达到 start/stop timeout 后:

1. 请求取消;
2. 在 cleanup timeout 内等待回调 task 真正结束;
3. task 已结束才进入同一插件的 `on_stop` 和 cleanup;
4. task 持续拒绝取消时, 不并发执行 `on_stop`/cleanup;
5. 保留 cleanup, 后续 `aclose()` 在 task 静默后继续清理.

回归覆盖了两种顺序:

```text
start entered -> cancel observed -> start exited -> stop
```

以及拒绝取消时:

```text
start entered -> cancel observed -> no concurrent stop
-> task exits -> later close runs retained cleanup
```

### 3.3 Beta 契约定位

- 版本更新为 `3.1.0b1`;
- 插件作者面统一称为 Beta/provisional, 不再同时声称“实验”和“稳定”;
- Beta 变更必须同步 changelog、文档、API snapshot 和外部 wheel fixture;
- RC 冻结作者 API; 正式稳定版发布后开始遵守 SemVer;
- 插件示例和 fixture 使用 `>=3.1.0b1,<3.2`;
- README 明确 Beta 不承诺无人值守生产或第三方 Source 自动发现.

## 4. 本地发布级证据

### 4.1 Python 和质量门禁

| 验证 | 结果 |
| --- | --- |
| Python 3.12 全量测试 | `717 passed` |
| Python 3.13 全量测试 | `717 passed` |
| Python 3.14 全量测试 | `717 passed` |
| 总 branch coverage | `83.02%` |
| Bilibili branch coverage | `83.96%` |
| NapCat branch coverage | `86.97%` |
| WebSocket branch coverage | `88.59%` |
| CLI runtime branch coverage | `80.36%` |
| Ruff check / format | 通过 |
| Pyright | 0 error / 0 warning |
| VuePress / Markdown / links | 50 页构建、lint、内部链接全部通过 |

Python 3.14 还暴露了测试依赖对象析构时机释放 logging lease 的问题. 相关测试已经
改为显式选择 external logging ownership, 不再依赖解释器何时执行 `__del__`.
同时把 Python 3.14 已弃用的 `asyncio.iscoroutinefunction()` 替换为
`inspect.iscoroutinefunction()`.

### 4.2 构建和隔离安装

在新建临时目录与干净 venv 中完成:

- 构建 `butterbot_python-3.1.0b1` wheel 与 sdist;
- 只安装基础 wheel 并执行 `scripts/smoke_wheel.py`;
- 验证基础依赖没有 `aiohttp` 或 Bilibili SDK;
- 验证缺少 NapCat/Bilibili extra 时通过公开配置路径返回可执行安装提示;
- 分别安装 `[napcat]`、`[bilibili]`、`[all]` 并通过各自 smoke;
- 构建并安装外部 Handler 插件 wheel;
- 验证外部插件成功启动、注册失败、应用 Source 启动失败和幂等关闭;
- 验证本地目录插件在不同绝对路径下均可加载和路由;
- 验证构建元数据版本为 `3.1.0b1`, PyPI README 不包含内部规划便笺.

### 4.3 版本通道

release workflow 的本地正则验收结果:

| 版本 | 通道 |
| --- | --- |
| `3.1.0.dev2` | prerelease |
| `3.1.0b1` | prerelease |
| `3.1.0rc1` | prerelease |
| `3.1.0` | stable |
| `3.1.0-beta.1` | rejected, 非项目采用的 PEP 440 格式 |

## 5. Beta 发布边界

本次 GO 不改变以下事实:

- 第三方 Source 没有自动 entry point 或 YAML factory 发现;
- 插件是可信进程内代码, 不是安全沙箱;
- 插件只注册 Handler 和管理自身资源, 不创建或接管 Source;
- EventBus 的 `max_pending_callbacks` 默认仍为 `None`, 生产试运行应显式评估上限;
- Bilibili danmaku 运行期断线尚无自动 worker 重建;
- Bilibili polling 连续失败的健康投影仍需后续增强;
- CLI 后台 stdout/stderr 文件尚不轮转;
- 没有真实 NapCat/Bilibili 联调、24 小时或 7 天 soak 证据;
- 没有热重载、远程控制面、多实例 supervisor 或不可信插件隔离.

这些项目阻断 RC 或无人值守承诺, 但在发布说明明确“受控真实环境 Beta、允许人工
观察和重启”的前提下, 不再阻断本次 Beta.

## 6. 发布前剩余动作

代码与本地验证已经达到 Beta GO. 真正发布前仍需:

1. 人工复核本地 diff 和版本/changelog;
2. 按关注点拆分并提交当前工作区;
3. 推送 `dev_main`, 等待远端 Python 3.12/3.13/3.14 与 docs CI 全绿;
4. 从包含 `3.1.0b1` 的 `dev_main` 提交创建 `v3.1.0b1` tag;
5. 确认 PyPI 上传和 GitHub prerelease 完成;
6. 发布说明保留第 5 节的 Beta 边界, 不宣称 RC、正式稳定或一周无人值守.

本次验收没有执行提交、tag、推送或发布.
