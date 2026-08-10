"""飞书 WebSocket 消息与机器人菜单事件示例。"""

from butterbot.app import BotApp
from butterbot.sources.lark import LarkSource, LarkType
from butterbot.sources.lark.events import LarkMenuEvent, LarkMessageReceiveEvent

app = BotApp()
source = app.get_source(LarkSource, "feishu_bot")
if source is None:
    raise RuntimeError("请先在 config.yaml 中启用 feishu_bot")


@app.subscribe(source.uuid, LarkType.MESSAGE_RECEIVE)
async def reply_message(event: LarkMessageReceiveEvent) -> None:
    """收到文本消息后引用回复。"""
    if event.data.message.message_type == "text":
        await event.data.reply_text("收到：%s" % event.data.message.text)


@app.subscribe(source.uuid, LarkType.MENU)
async def handle_menu(event: LarkMenuEvent) -> None:
    """响应机器人自定义菜单事件。"""
    await event.data.api.send_text(
        event.data.operator.operator_id.open_id or "",
        "菜单事件：%s" % event.data.event_key,
        receive_id_type="open_id",
    )


if __name__ == "__main__":
    app.run()
