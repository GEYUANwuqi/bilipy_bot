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

CLI 显式指定 `-config` 时必须使用工厂入口注入配置；对象入口
`app = BotApp()` 只适用于不指定 `-config`、由 `BotApp()` 构造时自动读取
`config.yaml` 的场景。

## `ConfigError: 缺少配置键`

确认：

1. `sources` 下的自定义实例键与 Source 的 `config_key` 一致；
2. `source_name: napcat` 正确构建为 `NapcatConfig`；
3. 自定义 `source_name` 已经注册 builder；
4. 值不是 `null`。

顶层 `napcat:`、`bilibili:` 等 Source 配置不再支持；加载错误中的迁移提示会指向
`sources.<config_key>.source_name`。

## `自动实例未注册` 或 `自动实例化失败`

确认 `kwarg` 的一级键是当前 `source_name` 已注册的 Source 类名，二级映射只包含
该类构造器支持的关键字参数。`config_key` 由外层实例键自动注入，不能重复填写。
内置类名清单见 [YAML 配置](/configuration/yaml.html)。

## `环境变量未设置且没有默认值`

`${NAME}` 要求当前进程环境或 YAML 的 `environment` 中存在 `NAME`。本地可声明
默认值，或使用 `${NAME:-default}`。若使用
`BUTTERBOT__SOURCES__实例键__字段` 直接覆盖，路径各段按小写配置键处理。

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

如果 `failures` 中包含 `rollback`，说明某个已启动 Source 的停止回调也失败；
先修正清理故障并调用 `await app.stop()`，再重新启动。

## `SourceStopError`

框架已经尝试停止全部 Source，但至少一个 `on_stop()` 失败。失败 Source 仍在
`app.manager.sources` 中，且 `cleanup_required=True`，不会被静默摘除。处理瞬时
故障后再次调用 `await app.stop()` 或 `await app.close()`。关闭重试完成前不要
创建新的 app 来复用同一组外部资源。

## Handler 抛错但发布方没有异常

这是 EventBus 的设计：Handler 在独立 task 中执行，异常记录到日志。启用日志：

```python
from butterbot.utils import setup_logging

setup_logging("DEBUG")
```

需要把业务失败返回发布方时，使用显式 Future/Queue 协议。
