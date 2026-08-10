---
title: API 参考
---

# API 参考

本栏目只手工维护稳定公开 API，不自动把内部类和 helper 生成为源码索引。

- [BotApp](./bot-app.md)
- [Event](./event.md)、[EventBus](./event-bus.md)
- [Subscriber](./subscriber.md)、[subscribe](./subscribe.md)
- [BaseFilter](./filter/base-filter.md)、[CombinedFilter](./filter/combined-filter.md)
- [BaseSource](./source/base-source.md)、[SourceManager](./source/source-manager.md)
- [BaseApi](./api/base-api.md)、[APIContext](./api/api-context.md)
- [Data / Type](./data-types.md)
- [Config](./config.md)
- [异常](./exceptions.md)
- [公共工具](./utilities.md)

## 收录规则

只有由稳定门面或明确 `__all__` 导出、文档承诺兼容性且有契约测试的符号进入本
栏目。下划线符号、DTO、解析 helper、WebSocket 内部状态和生命周期实现细节即使
可以导入，也不属于稳定 API。

- 稳定公开接口 → API 参考
- 内部实现和所有权 → [框架开发](/architecture/)
- 完成具体任务 → [功能指南](/features/)
- 编写新扩展 → [扩展开发](/extensions/)

普通应用优先从 `butterbot.app` 导入；扩展实现从对应的 `butterbot.core` 子模块
导入。项目按 SemVer 管理稳定 API 的不兼容变化。
