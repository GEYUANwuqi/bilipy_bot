from bilibili_api.live import LiveDanmaku
from bilibili_api import Credential
from bili_data import DanmakuMsgData
from bili_data import DanmakuMsgDTO

if __name__ == '__main__':
    import asyncio

    async def main():
        room_id = 192  # 替换为实际的直播间ID
        credential_uid = Credential(sessdata = "")
        danmaku = LiveDanmaku(room_display_id = room_id, credential = credential_uid)

        @danmaku.on('DANMU_MSG')
        async def on_danmaku(msg):
            dto_data = DanmakuMsgDTO.from_dict(msg)
            if dto_data:
                danmaku_data = DanmakuMsgData.from_dto(dto_data)
                print(danmaku_data)
            else:
                print(f"弹幕{msg}")

        @danmaku.on('SEND_GIFT')
        async def on_gift(msg):

            print(f"礼物{msg}")

        await danmaku.connect()
        await asyncio.sleep(1000)

    asyncio.run(main())
