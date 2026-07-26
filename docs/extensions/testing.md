---
title: 测试异步扩展
---

# 测试异步扩展

## 工具与模式

仓库使用 pytest、`pytest-asyncio`，并启用 strict 模式。异步测试显式标记：

```python
import pytest


@pytest.mark.asyncio
async def test_source_stops_its_task() -> None:
    ...
```

## Source 生命周期测试

使用不访问网络的替身上下文：

```python
from butter_bot.app import RuntimeConfig
from butter_bot.core.context import AppContext

source = MySource()
source.bind(AppContext(RuntimeConfig(my_service=FakeConfig())))

await source.start()
assert source.running

await source.stop()
assert not source.running
assert source._task is None
```

还应覆盖启动异常和 `CancelledError` 后 `running` 回滚，以及重复 start/stop。

## 事件测试

不要依赖任意 `sleep()` 等回调“碰巧完成”。使用 `asyncio.Event`：

```python
called = asyncio.Event()


async def handler(event: Event) -> None:
    called.set()


bus.add_subscriber(source.uuid, handler, MyType.READY, MyType)
await bus.publish(source.uuid, event)
await asyncio.wait_for(called.wait(), timeout=1.0)
await bus.close()
```

每个测试结束前关闭 EventBus，避免 strict 模式报告悬挂任务。

## API 测试

- 用 fake client 替代真实 WebSocket/HTTP；
- 用可观察计数验证 `aclose()`；
- 对 pending Future 测试成功路由、超时和取消；
- 使用 `asyncio.wait_for()` 给可能阻塞的测试设置上限；
- 不访问外部网络，不依赖测试顺序。

## 运行检查

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

最小示例的真实退出测试位于 `tests/test_examples.py`。新增完整示例时，优先把它
加入自动执行或至少语法/导入 smoke test。

## 常见失败

- `Task was destroyed but it is pending!`：创建者没有取消并等待任务；
- 测试偶发超时：用显式同步原语替代 sleep；
- strict 模式结束失败：listener、EventBus 或 API 未关闭；
- 捕获 `Exception` 没接住取消：`CancelledError` 需要单独处理。
