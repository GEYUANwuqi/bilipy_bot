from bilibili_api import Credential
from bilibili_api.user import User
from bili_data import DynamicData, DynamicDTO


async def get_all_dynamic(uid: int, sessdata: str = "", event: bool = True, file: bool = False) -> list[DynamicData]:
    """
    获取单页动态(谨慎使用)
    Args:
        uid (int): 用户uid
        sessdata (str): cookie信息-SESSDATA
        event (bool): 返回事件，默认True
        file (bool): 保存数据到本地文件，默认False
    Returns:
        list[DynamicData]: 动态信息对象
    """

    credential_uid = Credential(sessdata = sessdata)
    user = User(credential = credential_uid, uid = uid)
    dict_info = await user.get_dynamics_new()
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'all_dynamic.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(dict_info, f, ensure_ascii=False, indent=4)
    if event:
        info_dto = [DynamicDTO.from_dict(item) for item in dict_info["items"]]
        info = [DynamicData.from_dto(dto) for dto in info_dto if dto is not None]
    else:
        info = dict_info
        if not file:
            print(info)
    print(info)
    return info


async def get_new_dynamic(uid: int, sessdata: str = "", event: bool = True, file: bool = False) -> DynamicData:
    """获取最新的一条动态
    Args:
        uid (int): 用户uid
        sessdata (str): cookie信息-SESSDATA
        event (bool): 返回事件，默认True
        file (bool): 保存数据到本地文件，默认False
    Returns:
        DynamicData: 动态信息对象
    """

    credential_uid = Credential(sessdata=sessdata)
    user = User(credential = credential_uid, uid = uid)
    dict_info = await user.get_dynamics_new()
    dynamic_info = dict_info["items"][8]
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dynamic.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(dict_info, f, ensure_ascii=False, indent=4)
    if event:
        dto = DynamicDTO.from_dict(dynamic_info)
        info = DynamicData.from_dto(dto)
        print(info)
    else:
        info = dynamic_info
        if not file:
            print(info)
    return info

if __name__ == '__main__':
    import asyncio
    asyncio.run(
        get_new_dynamic(
            uid = 3546729546778833,
            sessdata = "",
            event = True,
            file = True
        ))
