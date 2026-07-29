---
title: 环境变量与安全边界
---

# 环境变量与安全边界

## 配置内引用

`RuntimeConfig.from_yaml()` 在每次加载时读取当前进程环境。YAML 字符串支持：

```yaml
sources:
  qq_account:
    source_name: napcat
    url: "${NAPCAT_URL}"
    token: "${NAPCAT_TOKEN:-}"
```

- `${NAME}`：变量必须存在，否则抛 `ConfigError`；
- `${NAME:-default}`：变量不存在或为空时使用默认值；
- 引用可以出现在较长字符串中，例如 `"prefix-${INSTANCE_ID}"`。

环境变量替换发生在 builder 之前。普通环境变量值保持字符串类型。

## YAML 中声明环境变量

本地开发可以在 `environment` 中声明当前配置使用的默认值：

```yaml
environment:
  NAPCAT_HOST: localhost
  NAPCAT_URL: "ws://${NAPCAT_HOST}:3001"
  NAPCAT_TOKEN: ""

sources:
  qq_account:
    source_name: napcat
    url: "${NAPCAT_URL}"
    token: "${NAPCAT_TOKEN}"
```

当前进程环境中的同名变量优先于 YAML 声明。`environment` 支持引用其他已声明变量
或进程变量，循环引用会抛 `ConfigError`。

这些值只参与本次 `RuntimeConfig` 加载，不会写入或修改全局 `os.environ`。因此
同一进程可以用不同 `environ` 快照构建多个相互隔离的配置，也不会意外影响日志库
或第三方 SDK。

## 分层环境变量覆盖

以 `BUTTERBOT__` 开头的变量按双下划线映射到 YAML 路径：

```bash
export BUTTERBOT__SOURCES__QQ_ACCOUNT__URL="ws://napcat:3001"
export BUTTERBOT__SOURCES__QQ_ACCOUNT__TOKEN="secret"
export BUTTERBOT__SOURCES__QQ_ACCOUNT__HEARTBEAT="15.0"
export BUTTERBOT__SOURCES__BILI_ACCOUNT__KWARG__BILIDANMAKUSOURCE__ROOM_ID="[1, 2]"
```

路径段转换为小写；Source 工厂类名在 `BotApp` 解析时不区分大小写。因此以上前三
项覆盖：

```yaml
sources:
  qq_account:
    url: "ws://napcat:3001"
    token: "secret"
    heartbeat: 15.0
```

分层覆盖发生在 `${NAME}` 替换之后，并可补充 YAML 中不存在的字段或完整 Source。
覆盖值使用 YAML 语义解析，所以 `15.0`、`true`、`null`、列表和映射会保留对应
类型；要强制保留容易被解析的字符串，可在环境变量值中包含 YAML 引号。

可以为嵌入式入口或后续 CLI 指定环境快照和前缀：

```python
config = RuntimeConfig.from_yaml(
    "config.yaml",
    environ={"APP__SOURCES__QQ_ACCOUNT__TOKEN": "secret"},
    env_prefix="APP__",
)
```

传入 `environ` 后不会再读取 `os.environ`。配置优先级从高到低为：

1. 分层环境变量覆盖；
2. `${NAME}` 引用的进程环境值；
3. YAML `environment` 默认值；
4. YAML 字段值；
5. 配置对象自身默认值。

`RuntimeConfig()` 仍然只是内存键值容器，不会读取环境。

## 日志工具使用的环境变量

`butterbot.utils.setup_logging()` 独立读取：

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

- 本地开发：使用被忽略的根目录 `config.yaml` 提供空值或非敏感默认值；
- CI/容器：从 Secret store 注入环境变量；
- 不打印完整配置对象或 Authorization header；
- 排障日志应先移除 Token、Cookie 和用户标识；
- 环境变量降低了 Secret 落盘风险，但不是加密存储或权限隔离机制。
