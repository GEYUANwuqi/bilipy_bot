---
title: 配置参考
---

# 配置参考

Butter-Bot 的应用配置由 `RuntimeConfig` 提供。它是轻量键值容器，不是 Pydantic
模型，也不自动读取环境变量。

- [RuntimeConfig](./runtime-config.md)
- [YAML 配置](./yaml.md)
- [环境变量与安全边界](./environment.md)

内置配置模板位于 `examples/config.example.yaml`。实际 `config.yaml` 已在
`.gitignore` 中忽略。
