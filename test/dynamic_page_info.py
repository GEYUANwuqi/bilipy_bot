from bilibili_api import Credential
from bilibili_api.dynamic import get_dynamic_page_info
from bili_data import DynamicData


async def get_new_dynamic_list(sessdata: str, event: bool = True, file: bool = False) -> list[DynamicData]:
    """获取动态主页的动态列表
    Args:
        sessdata (str): cookie信息-SESSDATA
        event (bool): 返回事件，默认True
        file (bool): 保存数据到本地文件，默认False
    Returns:
        list[DynamicData]: 动态信息对象
    """

    credential_uid = Credential(sessdata=sessdata)
    dynamic_info = await get_dynamic_page_info(credential_uid)
    info_list: list = dynamic_info["items"]
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dynamic_page_info.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(info_list, f, ensure_ascii=False, indent=4)
    if event:
        info = []
        for i in info_list:
            data = DynamicData(i)
            info.append(data)
        print(info)
    else:
        info = info_list
        if not file:
            print(info)
    return info

if __name__ == '__main__':
    import asyncio
    asyncio.run(
        get_new_dynamic_list(
            sessdata = "",
            event = True,
            file = True
        ))
