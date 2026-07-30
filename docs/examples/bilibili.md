---
title: Bilibili 示例
---

# Bilibili 示例

## 动态与直播状态

源码：
[`examples/plugins/manager_example/`](https://github.com/GEYUANwuqi/ButterBot/tree/dev_main/examples/plugins/manager_example)

```bash
cp examples/config.example.yaml config.yaml
uv run butterbot plugins list
uv run butterbot plugins check examples.plugin_app:create_app
uv run butterbot run examples.plugin_app:create_app
```

按目录内 README 启用插件，并让 YAML 创建 `BiliDynamicSource` 和
`BiliLiveSource`。插件通过 `SourceRef` 分别订阅动态变化、在线状态、开播与下播。
入口模块只定义一个 `ButterPlugin` 子类，由 loader 自动实例化，不需要
`create_plugin()`。Handler 作为插件实例方法注册，示例同时展示
`on_start()`/`on_stop()` 生命周期回调。

## 直播弹幕

源码：
[`examples/live_danmaku_example.py`](https://github.com/GEYUANwuqi/ButterBot/blob/dev_main/examples/live_danmaku_example.py)

```bash
uv run examples/live_danmaku_example.py
```

该示例使用 `BiliDanmakuSource` 并订阅开播事件。可根据
`DanmakuType.DANMAKU/GIFT/GUARD` 增加对应 Handler。

## 验证说明

两个示例均通过 AST 语法测试；manager 插件还通过真实 manifest 自动发现测试。
CI 不调用 Bilibili 网络，因此账号凭证、房间/用户 ID、上游限流、字段变化和线程
连接关闭需在实际环境验证。

## 建议

- 先使用单个目标和保守轮询间隔；
- 不要在 Handler 打印凭证或完整 Cookie；
- 关闭时观察是否出现房间线程退出超时；
- 上游请求错误先区分凭证、目标不存在、限流和数据结构变化。
