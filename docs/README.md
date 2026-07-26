---
pageLayout: home
home: true
title: bilipy_bot
config:
  - type: hero
    full: false
    hero:
      name: bilipy_bot
      tagline: 异步、事件驱动的 Python 机器人框架
      text: 将外部数据输入抽象为事件源，通过类型安全的事件总线连接异步处理器。
      actions:
        - theme: brand
          text: 快速开始
          link: /guide/quick-start.html
        - theme: alt
          text: 查看 API
          link: /api/
        - theme: alt
          text: GitHub
          link: https://github.com/GEYUANwuqi/bilipy_bot
  - type: features
    features:
      - title: 明确的异步生命周期
        icon: material-symbols:cycle
        details: BotApp 统一启动事件源，并按固定顺序排空回调、关闭 API 资源。
      - title: 事件与订阅
        icon: material-symbols:event-available-outline
        details: 使用 BaseType 声明状态，通过枚举、正则和内容过滤器注册异步回调。
      - title: 可扩展事件源
        icon: material-symbols:extension-outline
        details: 基于 BaseSource、BaseApi 与 AppContext 接入新的平台或数据输入。
      - title: 内置适配
        icon: material-symbols:hub-outline
        details: 当前仓库提供 NapCat 与 Bilibili 的事件源、数据模型和 API 封装。
  - type: custom
---

## 最小安装

```bash
uv add bilipy-bot
```

项目要求 Python 3.12 或更高版本。仓库开发环境使用 `uv` 和锁文件管理。

## 最小运行模型

下面的结构展示了推荐入口。完整、可直接运行且不依赖外部服务的版本见
[快速开始](/guide/quick-start.html)。

```python
import asyncio

from bilipy_bot.app import BotApp, RuntimeConfig


async def main() -> None:
    app = BotApp(RuntimeConfig())
    async with app:
        # 在这里等待业务完成，或由事件源持续产生事件。
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
```

::: warning 生命周期
`stop()` 只停止事件源；`close()` 还会排空事件回调并释放 API 资源。
应用所有权在当前函数中时，优先使用 `async with app`。
:::

## 从哪里开始

- 第一次使用：从[安装](/guide/installation.html)和[快速开始](/guide/quick-start.html)开始。
- 接入 NapCat 或 Bilibili：查看[功能指南](/features/)。
- 开发自定义事件源：查看[扩展开发](/extensions/)。
- 查询签名和异常：查看[API 参考](/api/)。
- 排查关闭、超时或悬挂任务：查看[故障排除](/troubleshooting/)。
