from bilibili_api.live import LiveDanmaku
from bilibili_api import Credential

if __name__ == '__main__':
    import asyncio

    async def main():
        room_id = 60989  # 替换为实际的直播间ID
        credential_uid = Credential(sessdata = "")
        danmaku = LiveDanmaku(room_display_id = room_id, credential = credential_uid)

        @danmaku.on('DANMU_MSG')
        async def on_danmaku(msg):
            print(f"弹幕{msg}")

        @danmaku.on('SEND_GIFT')
        async def on_gift(msg):
            print(f"礼物{msg}")

        await danmaku.connect()
        await asyncio.sleep(1000)

    asyncio.run(main())