---
title: 自定义 Data / Type
---

# Data 与 Type

## Type 契约

事件状态枚举继承 `BaseType`，值必须能按第一个 `.` 分成 scope 和 state：

```python
from butterbot.core.types import BaseType


class FeedType(BaseType):
    ALL = "feed.all"
    ITEM = "feed.item"
    ITEM_CREATED = "feed.item.created"
    ITEM_DELETED = "feed.item.deleted"
```

`ALL` 不是强制名称，但 `state == "all"` 的成员会作为通配规则，且不会作为具体
可派发状态返回。父状态 `ITEM` 可以匹配下级 `ITEM_CREATED`。

每个 Source 必须把枚举类赋给 `supported_types`，否则订阅注册会抛 `TypeError`。

## Data 选择

简单、可信的领域对象可组合 dataclass 与 `BaseDataMixin`：

```python
@dataclass
class FeedItem(BaseDataMixin):
    item_id: str
    text: str
```

外部字典需要验证时继承 `BaseDataModel`：

```python
class FeedPayload(BaseDataModel):
    item_id: str
    text: str
```

Pydantic 模型默认可转换类型、冻结实例并忽略额外字段。若这不符合扩展协议，应在
具体模型中覆盖 `model_config`，并通过测试固定行为。

## 自动分发

`BaseDataModel.from_dict()` 支持一层或多层 discriminator 注册。根类声明
`discriminator_field`，叶子声明 `discriminator_value`。未知值与字段缺失均抛
`ValueError`。

这套元类是框架内部约定，不等同于 Pydantic 官方 union。使用时应测试：

- 每个 discriminator 值注册到预期子类；
- 间接继承仍能注册；
- 未知值不会落入错误类型；
- `AutoDispatchList` 能分发列表元素。

## Event 类型注解

```python
event: Event[FeedItem] = Event(
    data=FeedItem(item_id="1", text="hello"),
    status=FeedType.ITEM_CREATED,
)
```

泛型帮助静态检查，不会在 `Event` 构造时自动验证 status 与 data 的对应关系。

## 兼容性

事件状态字符串、公开 Data 字段和类型含义都会进入用户 Handler。发布扩展版本时，
新增可选状态通常兼容；删除/重命名状态或必需字段应视为破坏性变更。
