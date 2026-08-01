# 工具模块

## 日志所有权

导入 `butterbot.utils` 不会修改 root logger 或创建日志文件.
`BotApp` 默认自动取得 managed 日志 lease, 普通用户只需要使用
`logging.getLogger(...)`. 嵌入已配置日志的宿主时, 构造
`BotApp(..., logging_mode="external")`.

只在不使用 `BotApp` 但需要复用 ButterBot 格式时手工取得 lease:

```python
from butterbot.utils import setup_logging

with setup_logging("DEBUG"):
    run_standalone_component()
```

相同配置共享 handler 和引用计数. 最后一份 lease 关闭时恢复宿主
logger 状态; 并存期间请求不同配置会直接报错.
日志文件名和 `LOG_REDIRECT_RULES` 中的重定向文件名必须位于 `LOG_FILE_PATH`
目录内；绝对路径或包含 `..` 的目录逃逸路径会直接报错。
