import asyncio
from bilibili_api import Credential
from bilibili_api.user import User
from event import DynamicData


async def get_new_dynamic(uid:int, sessdata:str = "", file:bool = False) -> DynamicData:
    """获取最新的一条动态
    Args:
        uid (int): 用户uid
        sessdata (str): cookie信息-SESSDATA
        file (bool): 保存数据到本地文件，默认False
    Returns:
        DynamicData: 动态信息对象
    """

    credential_uid = Credential(sessdata=sessdata)
    user = User(credential = credential_uid, uid = uid)
    dict_info = await user.get_dynamics_new()
    dynamic_info = dict_info["items"][0]
    info = DynamicData(dynamic_info)
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dynamics_info.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(dict_info, f, ensure_ascii=False, indent=4)
    return info

if __name__ == '__main__':
    asyncio.run(get_new_dynamic(uid = 1802011210, sessdata = "", file = True))