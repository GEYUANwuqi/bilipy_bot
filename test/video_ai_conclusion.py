from bilibili_api import Credential
from bilibili_api.video import Video
from bili_data import VideoPartData, VideoPartDto


async def get_video_ai_conclusion(
    bv_id: str,
    event: bool,
    sessdata: str,
    file: bool = False,
    text: bool = False
) -> dict:
    """获取视频ai总结信息
    视频必须要有AI字幕功能，才可以获取到
    Args:
        bv_id (str): 视频BV号
        event (bool): 返回事件
        sessdata (str): cookie信息-SESSDATA
        file (bool): 保存数据到本地文件，默认False
        text (bool): 保存字幕到本地文件，默认False
    Returns:
        dict: 视频AI总结信息对象
    """
    # TODO: 需要用一个sqlite，还得建立索引，专门存ts/text这一类，然后中间体使用类封装一下, 还可以考虑 bisect — 数组二分算法
    credential_uid = Credential(sessdata=sessdata)
    video = Video(credential = credential_uid, bvid = bv_id)
    info = await video.get_ai_conclusion(page_index = 0)
    if file:
        import json
        import os
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_ai_conclusion_.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
    if event:
        info_list = info["model_result"]["subtitle"][0]["part_subtitle"]
        info_dto = VideoPartDto.from_list(info_list)
        data = VideoPartData.from_dto_list(info_dto)
        texts = [con.content for con in data]
        content = "\n".join(texts)
        print(content)
    if text:
        import os
        texts = ""
        text_list = info["model_result"]["subtitle"][0]["part_subtitle"]
        for item in text_list:
            texts += item["content"] + "\n"
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_ai_conclusion_text.txt')
        with open(file_path, 'w', encoding = 'utf-8') as f:
            f.write(texts)
    # else:
    #     print(info)
    return info

if __name__ == '__main__':
    import asyncio
    asyncio.run(get_video_ai_conclusion(
        bv_id = "BV1dYitBcEqe",
        event = True,
        sessdata = "",
        file = False,
        text = False
        ))
