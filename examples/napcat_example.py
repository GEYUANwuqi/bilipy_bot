"""NapCat 使用示例

演示如何使用 BotApp 管理 NapCat 事件源：
1. 创建 BotApp 和 NapcatSource
2. 注册各种事件订阅者（群消息、私聊消息、通知、请求、元事件）
3. 管理生命周期
"""

import asyncio
from logging import getLogger

from butterbot.app import BotApp
from butterbot.sources.napcat import NapcatApi, NapcatSource, NapcatType
from butterbot.sources.napcat.data import (
    NapcatFriendRequestData,
    NapcatGroupMessageData,
    NapcatGroupRequestData,
    NapcatHeartbeatMetaData,
    NapcatLifecycleMetaData,
    NapcatPrivateMessageData,
)
from butterbot.sources.napcat.events import (
    NapcatEvent,
    NapcatFriendRequestEvent,
    NapcatGroupMessageEvent,
    NapcatGroupRequestEvent,
    NapcatHeartbeatMetaEvent,
    NapcatLifecycleMetaEvent,
    NapcatNoticeEvent,
    NapcatPrivateMessageEvent,
)
from butterbot.sources.napcat.filters import CommandFilter

_log = getLogger("NAPCAT")


# ============ 配置 ============ #
#
# 请先在仓库根目录运行以下命令，再填入你的配置:
#   cp examples/config.example.yaml config.yaml
#   sources:
#     qq_account:
#       source_name: napcat
#       kwarg:
#         NapcatSource: {}
#       url: "ws://localhost:3001"
#       token: ""
#
# BotApp 会自动读取 config.yaml，无需手动创建 RuntimeConfig。

# 创建 BotApp（自动加载 config.yaml）
app = BotApp()

# ============ 获取配置自动创建的事件源 ============ #
napcat_source = app.get_source(NapcatSource, "qq_account")
assert napcat_source is not None
napcat_id = napcat_source.uuid
napcat_api = app.get_api(NapcatApi, "qq_account")

# ============ 订阅群消息事件 ============ #


@app.subscribe(napcat_id, NapcatType.MESSAGE)
async def handle_group_message(
    event: NapcatGroupMessageEvent | NapcatPrivateMessageEvent,
):
    """处理所有消息（群消息和私聊消息）"""
    data = event.data

    if isinstance(data, NapcatGroupMessageData):
        # 提取纯文本内容
        plain_text = data.message.plain_text
        sender_name = data.sender.card or data.sender.nickname
        _log.info(f"[群消息] 群 {data.group_id} - {sender_name}: {plain_text}")

    elif isinstance(data, NapcatPrivateMessageData):
        plain_text = data.message.plain_text
        _log.info(f"[私聊消息] {data.sender.nickname} ({data.user_id}): {plain_text}")


@app.subscribe(
    napcat_id,
    NapcatType.MESSAGE,
    event_filter=CommandFilter("/help", "/status"),
)
async def handle_command(
    event: NapcatGroupMessageEvent | NapcatPrivateMessageEvent,
):
    """示例：使用精确命令过滤器处理命令."""
    data = event.data
    text = data.message.plain_text
    command = text.split(maxsplit=1)[0]
    _log.info(f"检测到命令: {command}")

    if command == "/help":
        _log.info("  → 执行帮助命令")
        await data.reply("可用命令：/help、/status")
    elif command == "/status":
        _log.info("  → 执行状态命令")
        # 获取客户端指标
        metrics = napcat_api.get_metrics()
        _log.info(f"  → 客户端指标: {metrics}")
        await data.reply("服务运行中")


# ============ 订阅通知事件 ============ #


@app.subscribe(napcat_id, NapcatType.NOTICE)
async def handle_notice(event: NapcatNoticeEvent):
    """处理通知事件（如群成员变动、消息撤回等）"""
    data = event.data
    _log.info(f"[通知事件] 类型: {data.notice_type}, 时间: {data.time}")


# ============ 订阅请求事件 ============ #


@app.subscribe(napcat_id, NapcatType.REQUEST)
async def handle_request(
    event: NapcatFriendRequestEvent | NapcatGroupRequestEvent,
):
    """处理请求事件（如加好友、加群请求）"""
    data = event.data

    if isinstance(data, NapcatFriendRequestData):
        _log.info(f"[好友请求] 用户 {data.user_id} 请求添加好友")
        _log.info(f"  验证信息: {data.comment}")
        _log.info(f"  Flag: {data.flag}")
        # await data.approve(remark="ButterBot")

    elif isinstance(data, NapcatGroupRequestData):
        _log.info(f"[群请求] 用户 {data.user_id} 请求加群 {data.group_id}")
        _log.info(f"  子类型: {data.sub_type}")
        _log.info(f"  验证信息: {data.comment}")
        _log.info(f"  Flag: {data.flag}")
        # await data.reject(reason="暂不接收新成员")


# ============ 订阅元事件（心跳和生命周期）============ #


@app.subscribe(napcat_id, NapcatType.META)
async def handle_meta_event(
    event: NapcatHeartbeatMetaEvent | NapcatLifecycleMetaEvent,
):
    """处理元事件"""
    data = event.data

    if isinstance(data, NapcatHeartbeatMetaData):
        # 心跳事件
        interval = data.interval
        _log.debug(f"[心跳] 间隔: {interval}ms")

    elif isinstance(data, NapcatLifecycleMetaData):
        # 生命周期事件
        if data.sub_type == "enable":
            _log.info("[生命周期] 框架已启用")
        elif data.sub_type == "disable":
            _log.info("[生命周期] 框架已禁用")
        elif data.sub_type == "connect":
            _log.info("[生命周期] 连接已建立")
        else:
            _log.info(f"[生命周期] 未知类型: {data.sub_type}")


# ============ 订阅所有事件（用于调试）============ #


@app.subscribe(napcat_id, NapcatType.ALL)
async def handle_all_events(event: NapcatEvent):
    """捕获所有事件（用于调试）"""
    _log.info(f"[ALL] 收到事件: {event}")


# ============ 示例：定时任务 ============ #


async def periodic_task():
    """示例：定时发送消息"""
    await asyncio.sleep(10)  # 等待 10 秒后开始

    while app.running:
        try:
            # 示例：每 60 秒发送一条测试消息
            await asyncio.sleep(60)

            # 获取 NapCat API
            # api = napcat_source.api

            # 发送群消息示例
            # result = await api.send_group_message(
            #     group_id=123456789,
            #     message=[
            #         {"type": "text", "data": {"text": "这是一条定时消息"}}
            #     ]
            # )
            # _log.info(f"定时消息发送结果: {result}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            _log.error(f"定时任务错误: {e}")


app.run()
