# api/context&config — API 的配置和上下文管理

## 总览

- **RuntimeConfig = “原材料仓库”**
- **APIContext = “受控工厂 + 单例池”**
- 它们俩是 **配置 ≠ 实例** 的明确分离。

---

## 1. RuntimeConfig：配置的集中仓库

- **定位**：API 构造所需对象的注册表，仅负责存储和分发“原材料”，即API所需的cookie等配置项。
- **职责**：
  - 构造成功后只读、按 key 取（如 `config.bilibili`、`config.deepseek`）。
  - 存储 Credential、Token、dict、dataclass、第三方库对象等。
- **不负责**：
  - 不校验、不构造 API、不做单例、不管理生命周期、不做魔法推断。
- **简单来说**：
  - key -> value 映射表, value 可为任意类型, 但通常为 API 构造所需的参数对象,
    如 Credential、dict 等。
  - 特征：纯种缓存容器。
- **用法示例**：

```python
from bilibili_api import Credential
from api.context.config import RuntimeConfig

config = RuntimeConfig(
  bilibili = Credential(sessdata = "xxx", bili_jct = "yyy"),
  deepseek = {"key": "abc"},
)
# config.bilibili -> Credential 实例
# config.deepseek= -> dict
```

---

## 2. APIContext：API 实例的唯一工厂与单例池

- **定位**：在一个运行作用域内，保证 API 的唯一性，并负责创建它。
- **职责**：
  - API 单例池（同类 API 只创建一次，后续复用）。
  - API 与 RuntimeConfig 的桥梁（API 构造参数从 config 获取）。
  - 真正掌握 API 的地方。
- **用法示例**：

```python
from api.context.api_context import APIContext
from api.bili_api import BilibiliApi

ctx = APIContext(config)
api = ctx.get_api(BilibiliApi)
# 先查池，无则调用 cls.create(ctx) 构造，缓存并返回
```

- **调用链心智模型**：

```
main.py
 └── RuntimeConfig  /*存储配置*/
      └── APIContext  /*管理API*/
            ├── _instances  /*存储API*/
            └── get_api()  /*获取API*/
                  └── API.create(ctx)  /*创建API*/
                        └── ctx.config.xxx
```

---

## 3. 两者如何协作？

- Manager 持有 APIContext：`self.api_context = APIContext(config)`
- EventSource/Handler 通过 Manager 间接访问 APIContext。
- API 构造时只关心 ctx.config.xxx，不关心 config 结构。

---

## 4. 推荐的 API/Source/Handler 写法

### API
```python
class BilibiliApi(BaseApi):
    def __init__(self, credential):
        self.credential = credential
    @classmethod
    def create(cls, ctx: APIContext) -> "BilibiliApi":
        return cls(
            ctx.config.get_config("bilibili")
        )
```

### EventSource
```python
class BilibiliSource(EventSource):
    @property
    def api(self) -> BilibiliApi:
        return self.api_ctx.get_api(BilibiliApi, BilibiliApi.create)
```

### Handler
```python
class Manager:
    def get_api(self, api_cls):
        return self.api_context.get_api(api_cls, api_cls.create)

@manager.subscribe(...)
async def handler(evt):
    bili = manager.get_api(BilibiliApi)
```

---

## 5. 故障排查要点

- KeyError 检查配置键。
- 单例失效检查 APIContext/cls。
- 内存增长检查 _instances。

---

代码位置参考：
- `api/context/api_context.py`（实现）
- `api/context/config.py`（API配置）
- `api/bili_api.py`（API 工厂示例）

---
