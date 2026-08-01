# Changelog

本文件记录面向使用者的行为、API 和安装方式变化. 当前 R1 属于
`3.1.0.dev2` clean-break 收敛窗口.

## Unreleased

### Changed

- 开始收敛插件作者 API、运行时控制面和 adapter 安装边界.
- 项目自有中文文本将统一使用 ASCII 半角标点.

### Removed

- 删除未导出且无调用的 `SyncWebSocketClient`.
- 删除 CLI `close` 别名, 统一使用 `stop` 优雅停止.
- 删除已被 `logging.getLogger()` 取代的 `get_log()`.
- 删除未使用的 tqdm 包装器和 Pillow、requests、tqdm 直接依赖.
- R1 中删除的 provisional API 不提供兼容 alias 或弃用包装器.
