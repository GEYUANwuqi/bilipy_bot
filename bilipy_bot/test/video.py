from bilibili_api import Credential
from bilibili_api.video import Video


async def get_video_info(bv_id: str, sessdata: str, file: bool = False) -> dict:
    """获取视频信息
    Args:
        bv_id (str): 视频BV号
        sessdata (str): cookie信息-SESSDATA
        file (bool): 保存数据到本地文件，默认False
    Returns:
        dict: 视频信息对象
    """

    credential_uid = Credential(sessdata=sessdata)
    video = Video(credential = credential_uid, bvid = bv_id)
    info = await video.get_info()
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_info.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
    else:
        print(info)
    return info

if __name__ == '__main__':
    import asyncio
    asyncio.run(
        get_video_info(
        bv_id = "BV1w6BDBkEoD",
        sessdata = "",
        file = True
        )
    )
