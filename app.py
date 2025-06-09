from time import sleep
from bilibili_api import Credential
from bilibili_api import user
import os
import json
from logger import setup_logger
import subprocess
import asyncio
import aiohttp
import aiofiles

logger = setup_logger(filename='bot')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

async def getmax_tsid(date):
        """获取最大时间戳和对应的ID"""
        max_timestamp = int(0)
        max_id = None
        # 遍历items列表中的每个元素
        list = date["items"]
        for index, item in enumerate(list):
            timestamp = item["modules"]["module_author"]["pub_ts"]
            # 如果max_timestamp为None或者当前时间戳大于max_timestamp，则更新最大时间戳和对应的ID
            if timestamp > max_timestamp:
                max_timestamp = timestamp
                max_id = index
        return max_timestamp, max_id

async def loads_json(dy_dict, new_filename, old_filename):
    """异步处理并加载JSON文件"""
    if os.path.getsize(old_filename) == 0:
    # 如果 old.json 文件为空，则将数据写入 new.json 和 old.json 文件
        async with aiofiles.open(new_filename, "w", encoding="utf-8") as new_file, aiofiles.open(old_filename, "w", encoding="utf-8") as old_file:
            json.dump(dy_dict, new_file, ensure_ascii=False, indent=4)
            json.dump(dy_dict, old_file, ensure_ascii=False, indent=4)
    else:
    # 如果 old.json 文件不为空，则将 new.json 文件的内容移动到 old.json 文件中，并将新的数据写入 new.json 文件
        async with aiofiles.open(new_filename, "r", encoding="utf-8") as new_file:
            new_data = json.loads(await new_file.read())
        async with aiofiles.open(old_filename, "w", encoding="utf-8") as old_file:
            json.dump(new_data, old_file, ensure_ascii=False, indent=4)
        async with aiofiles.open(new_filename, "w", encoding="utf-8") as new_file:
            json.dump(dy_dict, new_file, ensure_ascii=False, indent=4)
    # 读取 new.json 和 old.json 文件的内容到变量中
    async with aiofiles.open(new_filename, "r", encoding="utf-8") as new_file, aiofiles.open(old_filename, "r", encoding="utf-8") as old_file:
        new_data = json.loads(await new_file.read())
        old_data = json.loads(await old_file.read())
    return new_data, old_data
    

async def bot():
    """动态机器人函数，获取动态并处理"""
    credential_uid = Credential(sessdata=config['bot']['sessdata'])
    dy_dict = await user.User.get_dynamics_new(self=user.User(uid=config['bot']['uid'], credential=credential_uid))
    new_data, old_data = await loads_json(dy_dict, "new.json", "old.json")
    
    new_maxts, new_maxid = await getmax_tsid(new_data)
    old_maxts, old_maxid = await getmax_tsid(old_data)
    id = int(0)
    go = False
    forward_dy = False
    forward_av = False
    pic = None

    if new_maxts > old_maxts :
        logger.info(f"最大的时间戳是: {new_maxts}, 对应的ID是: {new_maxid}")
        go = True
        id = new_maxid
    if "DYNAMIC_TYPE_FORWARD" in new_data["items"][id]["type"] :
        if "DYNAMIC_TYPE_AV" in new_data["items"][id]["orig"]["type"] :
            forward_av = True
        else:
            forward_dy = True
    elif "live_rcmd" in new_data["items"][id]["modules"]["module_dynamic"]["major"] :
        go = False
    
    if forward_dy and go :
        name = new_data["items"][0]["modules"]["module_author"]["name"]
        title = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
        name2 = new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
        url =  "www.bilibili.com/opus/" + str(new_data["items"][id]["id_str"][2:])
        other_url = new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
        text = f"【转发动态通知】\n{name}转发了{name2}的动态\n{title}\n动态地址:{url}\n原动态地址:{other_url}"
        logger.info("有转发")
    elif forward_av and go :
        name = new_data["items"][0]["modules"]["module_author"]["name"]
        title = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
        name2 = new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
        url =  "www.bilibili.com/opus/" + str(new_data["items"][id]["id_str"][2:])
        other_url = new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
        text = f"【转发视频通知】\n{name}转发了{name2}的视频\n{title}\n动态地址:{url}\n原视频地址:{other_url}"
        logger.info("有转发")
    elif "jump_url" in new_data["items"][id]["basic"] and go:
        name = new_data["items"][0]["modules"]["module_author"]["name"]
        title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["title"] or None
        content = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"] or None
        url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
        text = f"【动态通知】\n【{name}】发布了新动态\n{title}\n{content}\n动态地址:{url}"
        logger.info("有新动态")
    elif go :
        name = new_data["items"][0]["modules"]["module_author"]["name"]
        tab = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"] or None
        title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["title"] or None
        pic = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["cover"]
        url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
        text = f"【视频通知】\n【{name}】更新了新视频\n{tab}\n《{title}》\n视频地址:{url}"
        logger.info("有新视频")
    return text, pic

