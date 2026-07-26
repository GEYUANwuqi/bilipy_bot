---
title: YAML 配置
---

# YAML 配置

## 加载

```python
from bilipy_bot.app import RuntimeConfig

config = RuntimeConfig.from_yaml("config.yaml")
```

省略路径时读取当前工作目录的 `config.yaml`。`BotApp()` 没有收到 `config`
参数时会自动执行这一加载。

## 文件要求

YAML 顶层必须是映射：

```yaml
napcat:
  url: "ws://localhost:3001"
  token: ""

custom:
  enabled: true
```

处理规则：

1. 使用 `yaml.safe_load()`；
2. 顶层不是 `dict` 时抛 `ConfigError`；
3. 已注册键调用对应 builder；
4. 未注册键保留 YAML 解析后的原始值。

## 内置 builder

### `napcat`

构建 `NapcatConfig`：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 是 | 无 | WebSocket 地址 |
| `token` | `str \| null` | 否 | `null` | Authorization 值 |
| `heartbeat` | `float` | 否 | `30.0` | 客户端心跳间隔（秒） |
| `reconnect_attempts` | `int` | 否 | `5` | 重连尝试次数 |
| `receive_timeout` | `float` | 否 | `60.0` | 接收与请求等待超时（秒） |

### `bilibili`

把映射作为关键字参数传给 `bilibili_api.Credential`。可用字段由当前锁定的
`bilibili-api-python` 决定，仓库模板列出 `sessdata`、`bili_jct` 和 `buvid3`。

## 注册自定义 builder

```python
from dataclasses import dataclass

from bilipy_bot.app import RuntimeConfig, register_builder


@dataclass
class FeedConfig:
    endpoint: str
    interval: float = 30.0


def build_feed(value: dict) -> FeedConfig:
    return FeedConfig(**value)


register_builder("feed", build_feed)
config = RuntimeConfig.from_yaml("config.yaml")
```

builder 是进程级注册表；测试修改后应恢复原状态，避免用例之间泄漏。builder
抛出的普通异常会包装为 `ConfigError` 并保留 cause。

## 错误

| 现象 | 异常 |
| --- | --- |
| 文件不存在 | `FileNotFoundError` |
| YAML 语法错误 | `yaml.YAMLError` |
| 顶层不是映射 | `ConfigError` |
| builder 构建失败 | `ConfigError` |

## 安全

复制模板后只在本地填写 Token：

```bash
cp examples/config.example.yaml config.yaml
```

不要把实际配置粘贴到日志、Issue 或文档。仓库忽略根目录 `/config.yaml`，但其他
位置的同名文件不一定被忽略，提交前仍需检查 `git status`。
