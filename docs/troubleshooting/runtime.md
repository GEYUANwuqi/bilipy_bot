---
title: 配置、订阅与启动问题
---

# 配置、订阅与启动问题

## `配置文件不存在`

`BotApp()` 从当前工作目录读取 `config.yaml`，不是从 Python 文件所在目录读取。

```bash
pwd
cp examples/config.example.yaml config.yaml
```

不需要外部配置时显式传 `BotApp(RuntimeConfig())`。

## `ConfigError: 缺少配置键`

确认：

1. YAML 顶层键与 Source 的 `config_key` 一致；
2. `napcat` 正确构建为 `NapcatConfig`；
3. 多实例自定义键已经注册 builder 或手工构造；
4. 值不是 `null`。

## `SubscriptionError`

状态规则在 `supported_types` 中没有具体匹配。打印枚举值并检查：

- scope 是否正确；
- 字符串中的 `.` 是否按正则转义；
- 使用的是目标 Source 对应的枚举类型；
- 正则是否能 `fullmatch` 完整值。

## 回调不执行

依次检查：

1. Source 已先注册；
2. Handler 是 `async def`；
3. Source 已启动；
4. UUID 来自同一个 Source 实例；
5. status 匹配实际 `event.status`；
6. `event_filter.check()` 返回 True；
7. EventBus 尚未关闭。

## `SourceStartError`

检查 `failures` 中每个原始异常。框架已回滚成功启动的 Source，可以修复配置后
重试。常见原因是连接不可达、凭证缺失或 Source `on_start()` 抛异常。

## Handler 抛错但发布方没有异常

这是 EventBus 的设计：Handler 在独立 task 中执行，异常记录到日志。启用日志：

```python
from butterbot.utils import setup_logging

setup_logging("DEBUG")
```

需要把业务失败返回发布方时，使用显式 Future/Queue 协议。
