---
title: API 参考
---

# API 参考

本栏目手工维护高价值公共 API。判断公共边界时以包的 `__all__`、应用门面和测试
使用方式为准。

- [应用 API](./app.md)：`butterbot.app`
- [核心扩展 API](./core.md)：`butterbot.core` 及其子模块
- [内置事件源 API](./builtin-sources.md)
- [异常参考](./exceptions.md)
- [API 稳定性](./stability.md)

## 导入约定

普通应用优先从门面导入：

```python
from butterbot.app import BotApp, Event, RuntimeConfig
```

扩展实现从具体 core 子模块导入：

```python
from butterbot.core.api import BaseApi
from butterbot.core.source import BaseSource
```

顶层 `butterbot` 当前只公开 `__version__`。不要把“模块路径可访问”等同于稳定
公共 API；以下划线开头的符号和未导出的实现细节不在兼容承诺范围内。

## 稳定性说明

项目当前为 `3.1.0` 正式稳定版。Stable、experimental 和 internal 的边界，以及
SemVer 规则见 [API 稳定性](./stability.md)。
