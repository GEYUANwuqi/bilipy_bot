import os
from bilibili_api import Credential
from bilibili_api.live import LiveRoom
import asyncio
import json

async def get_room_info(sessdata:str):
    """获取直播间信息"""
    credential_uid = Credential(sessdata=sessdata)
    live = await LiveRoom.get_room_info(
        self=LiveRoom(credential=credential_uid, room_display_id=308543))
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_info.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(live, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    sessdata = ""
    #sessdata = ""
    asyncio.run(get_room_info(sessdata=sessdata))