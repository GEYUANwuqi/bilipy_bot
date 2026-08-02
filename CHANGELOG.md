# Changelog

本文件记录面向使用者的行为、API 和安装方式变化. 当前 R1 属于
`3.1.0.dev2` clean-break 收敛窗口.

## Unreleased

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
