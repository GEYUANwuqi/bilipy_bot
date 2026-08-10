---
title: subscribe
---

# subscribe

推荐通过 `BotApp.subscribe()` 使用：

```python
@app.subscribe(source.uuid, MyType.READY, event_filter=MyFilter())
async def on_ready(event: Event[MyData]) -> None:
    ...
```

```python
BotApp.subscribe(
    source_id: UUID,
    status: BaseType | str | Pattern[str],
    *,
    event_filter: BaseFilter | None = None,
) -> Callable
```

Source 必须已经注册并声明 `supported_types`。回调必须是协程函数；字符串与正则规则
使用完整匹配。底层 `EventBus.subscribe()` 还接受 `supported_types` 和 `owner_id`，
供框架扩展建立可撤销的所有者边界。
