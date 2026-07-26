---
title: 异常参考
---

# 异常参考

所有类型都可从 `bilipy_bot.app` 导入。

## 层级与触发点

| 异常 | 同时继承 | 典型触发点 |
| --- | --- | --- |
| `BilipyError` | `Exception` | 框架异常基类 |
| `ConfigError` | `ValueError` | YAML 顶层错误、builder 失败、必需配置缺失 |
| `LifecycleError` | `RuntimeError` | 在已关闭 manager 上添加/启动 Source |
| `SourceError` | `BilipyError` | Source 通用错误、未注册 Source |
| `SourceStartError` | `SourceError` | 批量启动一个或多个 Source 失败 |
| `ApiError` | `BilipyError` | 扩展可使用的 API 领域错误 |
| `SubscriptionError` | `ValueError` | 状态规则没有匹配任何具体状态 |

## `SourceStartError`

```python
try:
    await app.start()
except SourceStartError as exc:
    for source_name, cause in exc.failures.items():
        print(source_name, repr(cause))
```

`failures: dict[str, BaseException]` 保留事件源描述到原始异常对象的映射。抛出前
已成功启动的 Source 已回滚。

## 不属于 BilipyError 的错误

当前公共路径还会直接抛：

- `FileNotFoundError`：默认 YAML 文件不存在；
- `yaml.YAMLError`：YAML 语法错误；
- `TypeError`：同步 Handler、Source 构造参数错误、缺少 `supported_types`；
- `ValueError`：Source 不存在于订阅入口、数据 discriminator 错误、部分
  Bilibili 数据错误；
- `TimeoutError`：NapCat 请求或用户设置的等待超时；
- `asyncio.CancelledError`：任务取消。

不要只捕获 `BilipyError` 后假设覆盖所有第三方网络或数据错误。

## 错误边界

- Handler 异常由 EventBus 记录，不传播给 `publish()`；
- API 关闭异常由 registry 记录并忽略；
- Source 启动异常会聚合；
- 内置轮询的单目标运行异常被记录后继续；
- `CancelledError` 在清理完成后可能继续传播。
