---
title: 错误传播与边界
---

# 错误传播与边界

## 异常层级

框架主动定义的异常都继承 `ButterError`：

```text
ButterError
├── ConfigError (同时继承 ValueError)
├── LifecycleError (同时继承 RuntimeError)
├── SourceError
│   └── SourceStartError
├── ApiError
└── SubscriptionError (同时继承 ValueError)
```

## 各边界如何处理错误

### 配置加载

文件不存在时抛 `FileNotFoundError`；YAML 语法错误保留 `yaml.YAMLError`；
顶层不是映射或 builder 构建失败时抛 `ConfigError`，并保留原异常为 `__cause__`。

### Source 启动

单个 `BaseSource.start()` 原样传播 `on_start()` 的异常。批量启动由
`SourceManager` 聚合为 `SourceStartError`，并在 `failures` 中保留每个原异常。

### Source 运行

内置轮询 Source 在单个目标边界记录普通异常并继续循环。自定义 Source 是否
重试应由扩展明确决定，框架不会自动包装所有运行期异常。

### Handler

Handler task 的异常由 EventBus 记录，不会回传给 `publish()`。需要业务级确认时，
使用显式 Future/Queue，并自行定义结果和错误协议。

### API 关闭

`ApiRegistry.aclose_all()` 对单个 API 的关闭异常记日志后继续，保证其他 API 仍
能释放；最终清空缓存。

## 捕获建议

```python
from butter_bot.app import ButterError, ConfigError

try:
    app = BotApp()
    app.run()
except ConfigError as exc:
    print(f"配置错误：{exc}")
except ButterError as exc:
    print(f"框架错误：{exc}")
```

不要用宽泛 `except Exception: pass` 隐藏启动或关闭失败。

## 相关页面

- [异常 API 参考](/api/exceptions.md)
- [故障排除](/troubleshooting/)
- [生命周期](/guide/lifecycle.md)
