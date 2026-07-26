---
title: NapCat 示例
---

# NapCat 示例

源码：
[`examples/napcat_example.py`](https://github.com/GEYUANwuqi/Butter-Bot/blob/dev_main/examples/napcat_example.py)

## 准备

```bash
cp examples/config.example.yaml config.yaml
```

填写本地 NapCat WebSocket 地址与必要 Token，然后运行：

```bash
uv run examples/napcat_example.py
```

示例覆盖：

- 群消息与私聊消息；
- `CommandFilter` 精确命令过滤；
- 通知、请求和元事件；
- `NapcatApi.get_metrics()`；
- `NapcatType.ALL` 调试订阅；
- `app.run()` 的阻塞入口和关闭路径。

## 验证说明

仓库测试会解析语法、核对配置模板路径，并确认示例使用
`CommandFilter("/help", "/status")`。CI 不连接真实 NapCat，因此网络握手、认证和
消息收发需要在你的环境验证。

## 安全

示例中的群号和发送逻辑是占位说明。填入真实 Token 后不要提交 `config.yaml`，
也不要把完整事件原始数据直接公开到 Issue。
