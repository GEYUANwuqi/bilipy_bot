from time import sleep
from bilibili_api import Credential, sync
from bilibili_api.live import LiveRoom
import subprocess
from logger import setup_logger
import os
import json
import base64

logger = setup_logger(filename='live')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

async def live():
    """主函数，获取直播间信息并处理"""
    credential_uid = Credential(sessdata=config['live']['sessdata'])
    live = await LiveRoom.get_room_info(self=LiveRoom(credential=credential_uid, room_display_id=config['live']['room_display_id']))
    if os.path.getsize("old_live.json") == 0:
    # 如果 old_live.json 文件为空，则将数据写入 new_live.json 和 old_live.json 文件
        with open("new_live.json", "w", encoding="utf-8") as new_live, open("old_live.json", "w", encoding="utf-8") as old_live:
            json.dump(live, new_live, ensure_ascii=False, indent=4)
            json.dump(live, old_live, ensure_ascii=False, indent=4)
    else:
    # 如果 old_live.json 文件不为空，则将 new_live.json 文件的内容移动到 old_live.json 文件中，并将新的数据写入 new_live.json 文件
        with open("new_live.json", "r", encoding="utf-8") as new_live:
            new_data = json.load(new_live)
        with open("old_live.json", "w", encoding="utf-8") as old_live:
            json.dump(new_data, old_live, ensure_ascii=False, indent=4)
        with open("new_live.json", "w", encoding="utf-8") as new_live:
            json.dump(live, new_live, ensure_ascii=False, indent=4)
    # 读取 new_live.json 和 old_live.json 文件的内容到变量中
    with open("new_live.json", "r", encoding="utf-8") as new_live, open("old_live.json", "r", encoding="utf-8") as old_live:
        new_info = json.load(new_live)
        old_info = json.load(old_live)

    new_live_info = str(new_info["room_info"]["live_start_time"])
    old_live_info = str(old_info["room_info"]["live_start_time"])
    title = new_info["room_info"]["title"]
    name = new_info["anchor_info"]["base_info"]["uname"]
    romm_id = new_info["room_info"]["room_id"]
    pic_url = None
    online = False

    if new_live_info == "0" and old_live_info != "0":
        pic_url = new_info["room_info"]["cover"]
        logger.info("下播")
        live = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{romm_id}"
    elif new_live_info == "0" :
        live = f"未开播"
    elif new_live_info != "0" and old_live_info == new_live_info :
        live = f"开播中"
    else:
        pic_url = new_info["room_info"]["cover"]
        logger.info("上播")
        online = True
        live = f"\n【直播通知】\n{name}开播啦！\n{title}\n直播地址：https://live.bilibili.com/{romm_id}"

    if pic_url != None :
        # 对文本进行转义序列编码（保留\n等字符）
        logger.info(f"原始文本: {live}")
        encoded_text = base64.b64encode(live.encode('utf-8')).decode('ascii')
        logger.debug(f"编码后文本(Base64): {encoded_text}")
        if online:
            bat_text = f"python send_qq.py -t {encoded_text} -p {pic_url} -a 1"
        elif not online :
            bat_text = f"python send_qq.py -t {encoded_text} -p {pic_url} -a 0"

        process = subprocess.Popen(["start", "/wait", "cmd", "/c", bat_text], shell=True)
        logger.info(f"执行命令: {bat_text}")
        process.wait()
        logger.info("命令执行完毕")

if __name__ == "__main__":
    while True:
        try:
            sync(live())
        except Exception as e:
            logger.error(f"发生错误: {e}")
        logger.info(f"等待10秒")
        sleep(10)
