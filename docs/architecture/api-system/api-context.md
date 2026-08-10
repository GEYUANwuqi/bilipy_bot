---
title: APIContext
---

# APIContext

当前代码中的 APIContext 由 `AppContext.api_ctx` 暴露，其具体类型是 `ApiRegistry`。
它按 `(API 类, config_key)` 缓存实例，并通过 `require_config()` 在能力创建时给出明确
的缺失配置错误。

应用关闭时 `aclose_all()` 先清空缓存，再逐个关闭实例；单个普通异常不会阻断其他
实例清理，取消会在其余清理完成后重新传播。

公开接口见 [APIContext API](/api/api/api-context.md)。
