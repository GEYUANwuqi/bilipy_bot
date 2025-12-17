from bilibili_api import Credential
from bilibili_api.live import LiveRoom
import asyncio
from event import LiveData


async def get_room_info(room_id:int, sessdata:str = "", file:bool = False) -> LiveData:
    """获取直播间信息
    Args:
        room_id (int): 直播间ID
        sessdata (str): cookie信息-SESSDATA
        file (bool): 保存数据到本地文件，默认False
    Returns:
        LiveData: 直播间信息对象
    """

    credential_uid = Credential(sessdata=sessdata)
    live_room = LiveRoom(credential = credential_uid, room_display_id = room_id)
    live = await live_room.get_room_info()
    info = LiveData(live)
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_info.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(live, f, ensure_ascii=False, indent=4)
    return info

if __name__ == '__main__':
    asyncio.run(get_room_info(
        room_id = 26498147,
        sessdata = "",
        file = True
    ))
