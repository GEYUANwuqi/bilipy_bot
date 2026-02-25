"""NapCat 使用示例

演示如何使用 SourceManager 管理 NapCat 事件源：
1. 创建 SourceManager 和 NapcatSource
2. 注册各种事件订阅者（群消息、私聊消息、通知、请求、元事件）
3. 管理生命周期
"""
import asyncio
from logging import getLogger

from manager import SourceManager
from manager.context import RuntimeConfig
from napcat import (
    NapcatSource,
    NapcatConfig,
    NapcatType,
)
from event import Event
from napcat.data import (
    NapcatEvent,
    NapcatGroupMessageEvent,
    NapcatPrivateMessageEvent,
    NapcatNoticeEvent,
    NapcatFriendRequestEvent,
    NapcatGroupRequestEvent,
    NapcatHeartbeatMetaEvent,
    NapcatLifecycleMetaEvent,
)
from utils import setup_logging

# 设置日志级别
setup_logging("INFO")
_log = getLogger("NAPCAT")


# ============ 配置 ============ #

# NapCat 配置
napcat_config = NapcatConfig(
    url="",  # NapCat WebSocket 地址
    token=""
)

# 创建运行时配置
config = RuntimeConfig(
    napcat=napcat_config,
)

# 创建管理器
manager = SourceManager(config)

# ============ 创建事件源 ============ #
# 注册 NapCat 事件源并获取 UUID
napcat_source = manager.add_source(
    source_cls=NapcatSource,
)
napcat_id = napcat_source.uuid


# ============ 订阅群消息事件 ============ #

@manager.subscribe(napcat_id, NapcatType.MESSAGE)
async def handle_group_message(event: Event[NapcatGroupMessageEvent | NapcatPrivateMessageEvent]):
    """处理所有消息（群消息和私聊消息）"""
    data = event.data

    if isinstance(data, NapcatGroupMessageEvent):
        # 提取纯文本内容
        plain_text = data.message.plain_text
        sender_name = data.sender.card or data.sender.nickname
        _log.info(f"[群消息] 群 {data.group_id} - {sender_name}: {plain_text}")

    elif isinstance(data, NapcatPrivateMessageEvent):
        plain_text = data.message.plain_text
        _log.info(f"[私聊消息] {data.sender.nickname} ({data.user_id}): {plain_text}")


@manager.subscribe(napcat_id, NapcatType.MESSAGE)
async def handle_command(event: Event[NapcatGroupMessageEvent | NapcatPrivateMessageEvent]):
    """示例：简单的命令处理"""
    data = event.data
    text = data.message.plain_text

    # 检测命令
    if text.startswith("/"):
        command = text.split()[0]
        _log.info(f"检测到命令: {command}")

        if command == "/help":
            _log.info("  → 执行帮助命令")
            # 这里可以调用 API 发送回复
            # await napcat_source.api.send_group_message(...)

        elif command == "/status":
            _log.info("  → 执行状态命令")
            # 获取客户端指标
            metrics = napcat_source.api.get_metrics()
            _log.info(f"  → 客户端指标: {metrics}")


# ============ 订阅通知事件 ============ #

@manager.subscribe(napcat_id, NapcatType.NOTICE)
async def handle_notice(event: Event[NapcatNoticeEvent]):
    """处理通知事件（如群成员变动、消息撤回等）"""
    data = event.data
    _log.info(f"[通知事件] 类型: {data.notice_type}, 时间: {data.time}")


# ============ 订阅请求事件 ============ #

@manager.subscribe(napcat_id, NapcatType.REQUEST)
async def handle_request(event: Event[NapcatFriendRequestEvent | NapcatGroupRequestEvent]):
    """处理请求事件（如加好友、加群请求）"""
    data = event.data

    if isinstance(data, NapcatFriendRequestEvent):
        _log.info(f"[好友请求] 用户 {data.user_id} 请求添加好友")
        _log.info(f"  验证信息: {data.comment}")
        _log.info(f"  Flag: {data.flag}")
        # 这里可以调用 API 同意或拒绝请求

    elif isinstance(data, NapcatGroupRequestEvent):
        _log.info(f"[群请求] 用户 {data.user_id} 请求加群 {data.group_id}")
        _log.info(f"  子类型: {data.sub_type}")
        _log.info(f"  验证信息: {data.comment}")
        _log.info(f"  Flag: {data.flag}")


# ============ 订阅元事件（心跳和生命周期）============ #

@manager.subscribe(napcat_id, NapcatType.META)
async def handle_meta_event(event: Event[NapcatHeartbeatMetaEvent | NapcatLifecycleMetaEvent]):
    """处理元事件"""
    data = event.data

    if isinstance(data, NapcatHeartbeatMetaEvent):
        # 心跳事件
        interval = data.interval
        _log.debug(f"[心跳] 间隔: {interval}ms")

    elif isinstance(data, NapcatLifecycleMetaEvent):
        # 生命周期事件
        if data.sub_type == "enable":
            _log.info(f"[生命周期] 框架已启用")
        elif data.sub_type == "disable":
            _log.info(f"[生命周期] 框架已禁用")
        elif data.sub_type == "connect":
            _log.info(f"[生命周期] 连接已建立")
        else:
            _log.info(f"[生命周期] 未知类型: {data.sub_type}")


# ============ 订阅所有事件（用于调试）============ #

@manager.subscribe(napcat_id, NapcatType.ALL)
async def handle_all_events(event: Event[NapcatEvent]):
    """捕获所有事件（用于调试）"""
    _log.info(f"[ALL] 收到事件: {event}")


# ============ 示例：定时任务 ============ #

async def periodic_task():
    """示例：定时发送消息"""
    await asyncio.sleep(10)  # 等待 10 秒后开始

    while manager.running:
        try:
            # 示例：每 60 秒发送一条测试消息
            await asyncio.sleep(60)

            # 获取 NapCat API
            api = napcat_source.api

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


# ============ 主函数 ============ #

async def main():
    _log.info("=" * 60)
    _log.info("启动 NapCat SourceManager")
    _log.info("=" * 60)
    _log.info(f"WebSocket 地址: {napcat_config.url}")
    _log.info(f"心跳间隔: {napcat_config.heartbeat} 秒")
    _log.info(f"重连尝试次数: {napcat_config.reconnect_attempts}")
    _log.info("=" * 60)

    try:
        # 启动管理器
        await manager.start()
        _log.info("✅ 管理器已启动，开始监听事件...")

        # 创建定时任务（可选）
        # task = manager.create_task(periodic_task())

        # 保持运行
        _log.info("按 Ctrl+C 停止程序")
        try:
            # 无限运行，直到手动停止
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            _log.info("收到停止信号...")

    except Exception as e:
        _log.error(f"程序运行错误: {e}", exc_info=True)
    finally:
        # 清理资源
        _log.info("正在停止管理器...")
        await manager.stop()
        await manager.close()
        _log.info("✅ 程序已停止")


# ============ 使用上下文管理器的示例 ============ #

async def main_with_context_manager():
    """使用异步上下文管理器的方式"""
    _log.info("启动 NapCat 监控...")

    async with manager:
        _log.info("监控已启动，按 Ctrl+C 停止...")
        try:
            # 保持运行
            await asyncio.sleep(300)  # 运行 5 分钟
        except asyncio.CancelledError:
            _log.info("收到取消信号")

    _log.info("监控已停止")


if __name__ == "__main__":
    try:
        # 使用普通方式
        asyncio.run(main())

        # 或者使用上下文管理器方式
        # asyncio.run(main_with_context_manager())

    except KeyboardInterrupt:
        _log.info("程序被中断")
    except Exception as e:
        _log.error(f"程序异常: {e}", exc_info=True)
