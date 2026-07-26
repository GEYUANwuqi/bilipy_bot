---
title: Bilibili 示例
---

# Bilibili 示例

## 动态与直播状态

源码：
[`examples/manager_example.py`](https://github.com/GEYUANwuqi/ButterBot/blob/dev_main/examples/manager_example.py)

```bash
cp examples/config.example.yaml config.yaml
uv run examples/manager_example.py
```

示例注册 `BiliDynamicSource` 和 `BiliLiveSource`，分别订阅动态变化、在线状态、
开播与下播。

## 直播弹幕

源码：
[`examples/live_danmaku_example.py`](https://github.com/GEYUANwuqi/ButterBot/blob/dev_main/examples/live_danmaku_example.py)

```bash
uv run examples/live_danmaku_example.py
```

该示例使用 `BiliDanmakuSource` 并订阅开播事件。可根据
`DanmakuType.DANMAKU/GIFT/GUARD` 增加对应 Handler。

## 验证说明

两个文件均通过 AST 语法测试和配置模板路径检查。CI 不调用 Bilibili 网络，因此
账号凭证、房间/用户 ID、上游限流、字段变化和线程连接关闭需在实际环境验证。

## 建议

- 先使用单个目标和保守轮询间隔；
- 不要在 Handler 打印凭证或完整 Cookie；
- 关闭时观察是否出现房间线程退出超时；
- 上游请求错误先区分凭证、目标不存在、限流和数据结构变化。
