---
title: BaseApi
---

# BaseApi

导入：

```python
from butterbot.core.api import BaseApi
```

实现类必须提供：

```python
@classmethod
def create(cls, ctx: ApiRegistry, config_key: str) -> Self: ...

async def aclose(self) -> None: ...
```

`create()` 由容器同步调用；`aclose()` 默认无操作，有连接或后台任务的实现必须覆写且
保证幂等。
