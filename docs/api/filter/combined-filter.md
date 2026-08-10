---
title: CombinedFilter
---

# CombinedFilter

代码中的稳定组合类型名为 `AndFilter` 和 `OrFilter`，没有名为
`CombinedFilter` 的具体类：

```python
from butterbot.app import AndFilter, OrFilter

combined = AndFilter(filter_a, filter_b)
alternative = OrFilter(filter_a, filter_b)

# 等价写法
combined = filter_a & filter_b
alternative = filter_a | filter_b
```

两者都按传入顺序短路执行 `check(event)`，并通过公开的 `filters` 属性保存子过滤器。
