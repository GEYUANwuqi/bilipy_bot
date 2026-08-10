---
title: Data / Type
---

# Data / Type

## Data

导入：

```python
from butterbot.core.data import (
    AutoDispatchList,
    BaseDataMixin,
    BaseDataModel,
    BaseDataT,
)
```

| 符号 | 说明 |
| --- | --- |
| `BaseDataMixin` | 为普通对象提供紧凑 `repr` 的 mixin |
| `BaseDataModel` | 不可变、忽略额外字段的 Pydantic v2 基类 |
| `AutoDispatchList[T]` | 对列表元素执行 discriminator 分发的 RootModel |
| `BaseDataT` | 绑定到 `BaseDataMixin` 的类型变量 |

`BaseDataModel.from_dict(value)` 根据根类的 `discriminator_field` 和子类的
`discriminator_value` 分发；字段缺失或值未注册时抛出 `ValueError`。

## Type

导入：

```python
from butterbot.core.types import BaseType, BaseTypeT
```

`BaseType` 是字符串枚举基类。稳定类方法：

| 方法 | 说明 |
| --- | --- |
| `scope` / `state` | 拆分状态值的作用域和状态部分 |
| `matches(rule)` | 判断当前成员是否匹配枚举成员、字符串或正则规则 |
| `matching_statuses(rule)` | 将规则展开为当前枚举中的具体状态 |

字符串和正则均使用完整匹配。具体平台的 Data / Type 从对应事件源包导入，使用方式
见[事件源指南](/features/sources/)；自定义模型见
[自定义 Data / Type](/extensions/custom-data-types.md)。
