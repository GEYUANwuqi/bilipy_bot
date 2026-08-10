---
title: 基础示例
---

# 基础示例

源码：`examples/minimal_source_example.py`

```bash
uv run examples/minimal_source_example.py
```

预期输出：

```text
ready
```

@[code python](../../examples/minimal_source_example.py)

## 验证范围

`tests/test_examples.py::test_minimal_source_example_runs_and_exits_cleanly` 使用当前
Python 解释器启动子进程，要求：

- 5 秒内退出；
- 退出码为 0；
- 标准输出为 `ready`。

该路径覆盖 `asyncio.run()`、`BotApp` 创建、Source 注册、Handler 类型关系、
Source task 所有权、async context manager 与正常关闭。

## 改造成真实 Source

替换 `_publish_once()` 为外部监听循环时：

1. 保留 task 引用；
2. 在 `on_stop()` 取消并等待；
3. 每条原始输入先转换为 Data 和 BaseType；
4. 不在 Source 中直接调用业务 Handler；
5. 为取消、超时和连接异常增加测试。
