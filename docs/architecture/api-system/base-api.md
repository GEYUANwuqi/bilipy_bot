---
title: BaseApi
---

# BaseApi

`BaseApi` 定义“按配置键创建、由容器复用、应用关闭时释放”的外部能力契约。
`create()` 是同步工厂；需要网络连接的实现应延迟到首次异步调用或显式启动方法建立
连接。`aclose()` 必须幂等。

实现指南见 [自定义 API](/extensions/custom-api.md)，签名见
[BaseApi API](/api/api/base-api.md)。
