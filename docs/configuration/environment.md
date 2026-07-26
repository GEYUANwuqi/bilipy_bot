---
title: 环境变量与安全边界
---

# 环境变量与安全边界

## RuntimeConfig 不自动读取环境变量

当前实现没有 `BaseSettings`、`.env` 加载或字段到环境变量的映射。以下写法不会
自动进入 `RuntimeConfig`：

```bash
export NAPCAT_TOKEN="..."
```

需要环境变量时，由应用显式读取并构造配置对象：

```python
import os

from butter_bot.app import RuntimeConfig
from butter_bot.sources.napcat import NapcatConfig

config = RuntimeConfig(
    napcat=NapcatConfig(
        url=os.environ["NAPCAT_URL"],
        token=os.environ.get("NAPCAT_TOKEN"),
    )
)
```

不要为可选 Secret 提供会误连生产环境的硬编码默认值。

## 日志工具使用的环境变量

`butter_bot.utils.setup_logging()` 独立读取：

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 控制台日志级别 |
| `FILE_LOG_LEVEL` | `DEBUG` | 文件日志级别 |
| `LOG_FILE_PATH` | `./logs` | 日志目录 |
| `LOG_FILE_NAME` | `bot.log` | 日志文件名 |
| `BACKUP_COUNT` | `7` | 轮转保留数 |
| `LOG_REDIRECT_RULES` | `{}` | JSON 格式 logger 重定向规则 |

传给 `setup_logging(console_level=...)` 的值优先于 `LOG_LEVEL`。
`BACKUP_COUNT` 不是整数时会记录警告并回退到默认值。

## Secret 建议

- 本地开发：使用被忽略的根目录 `config.yaml`；
- CI/容器：从 Secret store 注入环境变量，再在应用入口显式构造
  `RuntimeConfig`；
- 不打印完整配置对象或 Authorization header；
- 排障日志应先移除 Token、Cookie 和用户标识。
