---
title: Config
---

# Config

应用层导入：

```python
from butterbot.app import RuntimeConfig, SourceDefinition, register_builder
```

`RuntimeConfig(**values)` 创建内存配置；`RuntimeConfig.from_yaml(path, *, environ=None,
env_prefix="BUTTERBOT__")` 加载 YAML、环境引用、分层覆盖和 Source 定义。

稳定读取接口是 `get_config(key, default=None)`。`source_definitions`、
`plugin_enabled` 等属性提供装配阶段的只读输入。自定义配置对象只需实现
`ConfigProvider.get_config()` 协议。

YAML、环境变量与 builder 细节见 [配置指南](/features/configuration/)。
