# Changelog

本文件记录面向使用者的行为、API 和安装方式变化。自 `3.1.0` 起，已文档化的公共
API 在 `3.x` 内遵守 SemVer 兼容承诺。

## 3.1.0 - 2026-08-04

### Stable release

- Source、API、Data、Type、Filter 与可信 Handler 插件的已文档化公共作者面成为
  stable API；同一 `3.x` 内不删除名称，也不破坏正确调用的签名或语义。
- 第三方 Source 保持由应用工厂显式装配；这不是临时限制，而是稳定的所有权边界。
- 仅明确标注为 experimental 的能力可在后续 minor 版本调整；internal 控制面不提供
  兼容承诺。

### Fixed

- NapCat WebSocket 认证按 OneBot 约定发送 `Authorization: Bearer <token>`，并加入
  回归测试。

## 3.1.0b1 - 2026-08-02

### Beta scope

- 自定义 Source 通过应用工厂和 `BotApp.add_source()` 手动装配; 本轮不提供第三方
  Source 自动发现或自动 YAML factory 注册.
- 插件只支持可信 Handler 行为扩展和自身资源, 不创建或接管 Source.
- 当前 Beta 用于受控真实环境验证, 不承诺服务器无人值守生产.

### Changed

- 开始收敛插件作者 API、运行时控制面和 adapter 安装边界.
- `BotApp` 默认自动管理日志格式, 并提供 `external` 模式保留宿主配置.
- `setup_logging()` 返回可共享且可恢复宿主状态的 `LoggingLease`.
- `butterbot.plugin` 只保留插件作者契约和可捕获异常.
- CLI 和直接运行统一为 `RuntimeConfig -> BotApp` 装配路线；CLI 工厂改为接收
  `config` 与 `cli_mode`.
- `BotApp` 新增只读 `plugin_enabled`、`cli_mode`，并根据最终配置动态导入插件运行时.
- `plugin check` 改在短生命周期子进程中校验候选代码.
- 内置 adapter 改为 `napcat`、`bilibili` 和 `all` extras;
  NapCat 与 Bilibili 均显式依赖 `aiohttp`.
- 项目自有中文文本将统一使用 ASCII 半角标点.

### Fixed

- 发布 wheel smoke 不再导入已经内部化的 `SourceFactoryRegistry`.
- WebSocket 发送取消不再阻塞回填满队列; 断线使用单一 in-flight slot 重放消息.
- 插件生命周期回调超时后先等待取消静默, 避免 `on_start` 与 `on_stop` 并发.
- release workflow 接受 PEP 440 `bN` 和 `rcN` 预发布版本.

### Removed

- 删除未导出且无调用的 `SyncWebSocketClient`.
- 删除 CLI `close` 别名, 统一使用 `stop` 优雅停止.
- 删除已被 `logging.getLogger()` 取代的 `get_log()`.
- 删除未使用的 tqdm 包装器和 Pillow、requests、tqdm 直接依赖.
- 删除未使用的公开 terminal 颜色生成器, 日志只保留私有最小 ANSI 能力.
- 从插件根包删除 discovery、bootstrap、manager、registrar 收据和状态模型.
- 删除 `ExtensionRegistrar` 和手工插件原型入口, 运行时只保留一份私有注册事务实现.
- 删除插件 `@configure`、`ConfigRegistrar`、Source builder/factory 注册和 Source
  创建、接管能力；插件只注册 Handler 和管理自身非 Source 资源.
- 删除 CLI 已构造对象入口和 `source_factory_registry` 工厂参数.
- 删除 source-only/combined 插件测试模式，保留应用 Source + Handler 插件契约.
- R1 中删除的 provisional API 不提供兼容 alias 或弃用包装器.
