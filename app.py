import os
import json
import asyncio
import aiofiles
from bilibili_api import Credential, user
from bilibili_api.live import LiveRoom
from logger import setup_logger

logger = setup_logger(filename='app')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

async def getmax_tsid(date):
    """获取最大时间戳和对应的ID"""
    max_timestamp = int(0)
    max_id = None
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
        async with aiofiles.open(new_filename, "w", encoding="utf-8") as new_file, \
                    aiofiles.open(old_filename, "w", encoding="utf-8") as old_file:
            await new_file.write(json.dumps(dy_dict, ensure_ascii=False, indent=4))
            await old_file.write(json.dumps(dy_dict, ensure_ascii=False, indent=4))
    else:
    # 如果 old.json 文件不为空，则将 new.json 文件的内容移动到 old.json 文件中，并将新的数据写入 new.json 文件
        async with aiofiles.open(new_filename, "r", encoding="utf-8") as new_file:
            new_data = json.loads(await new_file.read())
        async with aiofiles.open(old_filename, "w", encoding="utf-8") as old_file:
            await old_file.write(json.dumps(new_data, ensure_ascii=False, indent=4))
        async with aiofiles.open(new_filename, "w", encoding="utf-8") as new_file:
            await new_file.write(json.dumps(dy_dict, ensure_ascii=False, indent=4))
    
    # 读取 new.json 和 old.json 文件的内容到变量中
    async with aiofiles.open(new_filename, "r", encoding="utf-8") as new_file, \
                aiofiles.open(old_filename, "r", encoding="utf-8") as old_file:
        new_data = json.loads(await new_file.read())
        old_data = json.loads(await old_file.read())

    return new_data, old_data
    
async def send_qq(bat_text):
    """发送QQ消息"""
    logger.info(f"开始执行命令: {bat_text}")
    try:
        process = await asyncio.create_subprocess_shell(f'start /wait cmd /c {bat_text}')
        
        returncode = await process.wait()
        
        if returncode == 0:
            logger.info(f"命令执行成功")
        else:
            logger.error(f"命令执行失败，返回码: {returncode}")
            
    except Exception as e:
        logger.error(f"命令执行异常: {e}")

async def bot():
    """动态机器人函数，获取动态并处理"""
    try:
        user_obj = user.User(
            uid=config['bot']['uid'], 
            credential=Credential(sessdata=config['bot']['sessdata'])
        )
        
        dy_dict = await user_obj.get_dynamics_new()
        
        new_data, old_data = await loads_json(dy_dict, "new.json", "old.json")
        
        new_maxts, new_maxid = await getmax_tsid(new_data)
        old_maxts, old_maxid = await getmax_tsid(old_data)
        
        id = 0
        go = False
        forward_dy = False
        forward_av = False
        pic_url = None
        text = None

        if new_maxts > old_maxts:
            logger.info(f"最大的时间戳是: {new_maxts}, 对应的ID是: {new_maxid}")
            go = True
            id = new_maxid
        
        if go and "DYNAMIC_TYPE_FORWARD" in new_data["items"][id]["type"]:
            if "DYNAMIC_TYPE_AV" in new_data["items"][id]["orig"]["type"]:
                forward_av = True
            else:
                forward_dy = True
        elif go and "live_rcmd" in new_data["items"][id]["modules"]["module_dynamic"]["major"]:
            go = False
            logger.info("直播推荐动态，跳过处理")
        
        if forward_dy and go:
            name = new_data["items"][0]["modules"]["module_author"]["name"]
            title = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(new_data["items"][id]["id_str"][2:])
            other_url = new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【转发动态通知】\n{name}转发了{name2}的动态\n{title}\n动态地址:{url}\n原动态地址:{other_url}"
            logger.info("有转发")
        elif forward_av and go:
            name = new_data["items"][0]["modules"]["module_author"]["name"]
            title = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(new_data["items"][id]["id_str"][2:])
            other_url = new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【转发视频通知】\n{name}转发了{name2}的视频\n{title}\n动态地址:{url}\n原视频地址:{other_url}"
            logger.info("有转发")
        elif "jump_url" in new_data["items"][id]["basic"] and go:
            name = new_data["items"][0]["modules"]["module_author"]["name"]
            title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["title"] or None
            content = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"] or None
            url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【动态通知】\n【{name}】发布了新动态\n{title}\n{content}\n动态地址:{url}"
            logger.info("有新动态")
        elif go:
            name = new_data["items"][0]["modules"]["module_author"]["name"]
            tab = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"] or None
            title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["title"] or None
            pic_url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["cover"]
            url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【视频通知】\n【{name}】更新了新视频\n{tab}\n《{title}》\n视频地址:{url}"
            logger.info("有新视频")

        if go:
            return text, pic_url
        else:
            return None, None
            
    except Exception as e:
        logger.error(f"动态处理出错: {str(e)}")
        return None, None 

async def live():
    """直播间机器人函数，获取直播间信息并处理"""
    try:
        room = LiveRoom(
            credential=Credential(sessdata=config['live']['sessdata']), 
            room_display_id=config['live']['room_display_id'])
        
        live_dict = await room.get_room_info()
        
        new_info, old_info = await loads_json(live_dict, "new_live.json", "old_live.json")
        
        new_live_info = str(new_info["room_info"]["live_start_time"])
        old_live_info = str(old_info["room_info"]["live_start_time"])
        title = new_info["room_info"]["title"]
        name = new_info["anchor_info"]["base_info"]["uname"]
        room_id = new_info["room_info"]["room_id"]
        pic_url = None
        live_msg = None
        online = False

        if new_live_info == "0" and old_live_info != "0":
            pic_url = new_info["room_info"]["cover"]
            logger.info("下播")
            live_msg = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"
        elif new_live_info == "0":
            live_msg = f"未开播"
        elif new_live_info != "0" and old_live_info == new_live_info:
            live_msg = f"开播中"
        else:
            pic_url = new_info["room_info"]["cover"]
            logger.info("上播")
            online = True
            live_msg = f"\n【直播通知】\n{name}开播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"
            
        if pic_url is not None:
            return online, live_msg, pic_url
        else:
            return None, None, None
            
    except Exception as e:
        logger.error(f"直播间处理出错: {str(e)}")
        return None, None, None  

async def main():
    """主函数，获取直播间信息和动态信息并处理"""
    tasks = [
        asyncio.create_task(live()),
        asyncio.create_task(bot())
    ]
    results = await asyncio.gather(*tasks)

    live_data = results[0]
    bot_data = results[1]

    live_online, live_msg, live_pic = live_data
    dy_msg, dy_pic = bot_data
    
    if live_msg is not None:
        encoded_text = live_msg.encode('unicode_escape').decode('utf-8')
        if live_online is True:
            bat_text = f"python send_qq.py -t {encoded_text} -p {live_pic}"
        elif live_online is False:
            bat_text = f"python send_qq.py -t {encoded_text} -p {live_pic} -a 0"
        await send_qq(bat_text)
        
    if dy_msg is not None:
        if dy_pic is None:
            encoded_text = dy_msg.encode('unicode_escape').decode('utf-8')
            bat_text = f"python send_qq.py -t {encoded_text}"
        else:
            encoded_text = dy_msg.encode('unicode_escape').decode('utf-8')
            bat_text = f"python send_qq.py -t {encoded_text} -p {dy_pic}"
        await send_qq(bat_text)

async def main_loop():
    """主事件循环"""
    while True:
        try:
            await main()
        except Exception as e:
            logger.error(f"发生错误: {e}")
        logger.info("等待10秒")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main_loop())