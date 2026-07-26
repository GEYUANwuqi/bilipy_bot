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

项目版本为 `3.0.2`。仓库没有单独的 API 稳定性分级；因此本文只陈述当前行为，
不推测未来兼容周期。升级前应查看 Git 变更和测试，并关注：

- 导入路径；
- 方法签名；
- `BaseType` 状态字符串；
- Data 模型公开字段；
- 生命周期和异常传播。
