---
title: 数据模型
---

# 数据模型

## 两种基础形式

`BaseDataMixin` 为普通 Python 对象提供紧凑 `repr`，适合已经完成验证的数据：

```python
from dataclasses import dataclass

from bilipy_bot.core.data import BaseDataMixin


@dataclass
class Temperature(BaseDataMixin):
    value: float
```

`BaseDataModel` 基于 Pydantic v2，适合从外部字典验证和构造数据。当前配置为：

- `strict=False`：允许 Pydantic 支持的类型转换；
- `frozen=True`：实例不可变；
- `extra="ignore"`：忽略额外字段。

```python
from bilipy_bot.core.data import BaseDataModel


class UserPayload(BaseDataModel):
    user_id: int
    nickname: str


payload = UserPayload.model_validate({"user_id": "42", "nickname": "Ada"})
```

## discriminator 分发

框架的 `MetaDataModel` 支持基于类变量注册子类。分发根声明
`discriminator_field`，叶子声明 `discriminator_value`：

```python
from typing import ClassVar

from bilipy_bot.core.data import BaseDataModel


class Payload(BaseDataModel):
    discriminator_field: ClassVar[str] = "kind"


class TextPayload(Payload):
    discriminator_value: ClassVar[str] = "text"
    kind: str
    text: str


item = Payload.from_dict({"kind": "text", "text": "hello"})
assert isinstance(item, TextPayload)
```

字段缺失或值未注册时，`from_dict()` 抛出 `ValueError`。注册机制用于当前 NapCat
事件与消息段模型；它不是 Pydantic 官方 discriminated union 的别名。

## DTO 与领域数据

Bilibili 适配先用 Pydantic DTO 验证外部响应，再转换为面向业务的
`BaseDataMixin` 数据对象。这样可以把第三方字段变化与 Handler 使用的结构分开。

## 类型关系

`Event[T]` 的泛型参数就是事件数据类型：

```python
async def handler(event: Event[UserPayload]) -> None:
    print(event.data.user_id)
```

运行时不会根据泛型参数自动验证 `Event.data`；验证发生在数据构造阶段。

## 相关页面

- [事件、状态与处理器](./events-and-handlers.md)
- [开发数据模型](/extensions/data-and-types.md)
- [core API](/api/core.md)
