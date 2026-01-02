from bilibili_api.live import LiveDanmaku
from bilibili_api import Credential
from bili_data import DanmakuMsgData, DanmakuMsgDTO, DanmakuGiftDTO, DanmakuGiftData

if __name__ == '__main__':
    import asyncio

    async def main():
        room_id = 26498147  # 替换为实际的直播间ID
        credential_uid = Credential(sessdata = "")
        danmaku = LiveDanmaku(room_display_id = room_id, credential = credential_uid)

        @danmaku.on("LIVE")
        async def on_live(msg):
            print("直播开始了！")
            import json
            import os
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_sta.json')
            with open(file_path, 'w', encoding = 'utf-8') as f:
                json.dump(msg, f, ensure_ascii = False, indent = 4)
                #  实际数据量非常少, 仅仅作为信号就可以，接收到后应该再次调用get_room_info()
                #  下一步重构live_room_data

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
            dto_data = DanmakuGiftDTO.from_dict(msg)
            if dto_data:
                danmaku_data = DanmakuGiftData.from_dto(dto_data)
                print(danmaku_data)
            else:
                print(f"礼物{msg}")

        await danmaku.connect()
        await asyncio.sleep(1000)

    asyncio.run(main())
