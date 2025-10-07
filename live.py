import asyncio
import base64
import json
from bilibili_api import Credential
from bilibili_api.live import LiveRoom
from logger import setup_logger


logger = setup_logger(filename='live')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    configs:dict = json.load(config_file)

config = configs.get("live",{})
if not config:
    logger.error("未在config.json内找到live配置")
    raise SystemExit(1)

class BilibiliLive:
    def __init__(self):
        self.new_info = None
        self.old_info = None

    async def get_room_info(self):
        """获取直播间信息"""
        credential_uid = Credential(sessdata=config['sessdata'])
        live = await LiveRoom.get_room_info(
            self=LiveRoom(credential=credential_uid, room_display_id=config['room_display_id']))
        return live

    async def process_live_info(self):
        """处理直播间信息并发送通知"""
        live_info = await self.get_room_info()
        
        # 初始化数据
        if self.new_info is None:
            self.new_info = live_info
            self.old_info = live_info
            logger.debug(f"初始化数据{self.new_info}")
        
        # 更新数据
        self.old_info = self.new_info
        self.new_info = live_info

        new_live_info = str(self.new_info["room_info"]["live_start_time"])
        old_live_info = str(self.old_info["room_info"]["live_start_time"])
        title = self.new_info["room_info"]["title"]
        name = self.new_info["anchor_info"]["base_info"]["uname"]
        room_id = self.new_info["room_info"]["room_id"]
        pic_url = None
        online = False

        if new_live_info == "0" and old_live_info != "0":
            pic_url = self.new_info["room_info"]["cover"]
            logger.info("下播")
            live = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"
        elif new_live_info == "0":
            live = f"未开播"
        elif new_live_info != "0" and old_live_info == new_live_info:
            logger.debug("当前直播进行中")
            live = f"开播中"
        else:
            pic_url = self.new_info["room_info"]["cover"]
            logger.info("上播")
            online = True
            live = f"\n【直播通知】\n{name}开播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"

        if pic_url is not None:
            # 对文本进行转义序列编码（保留\n等字符）
            logger.info(f"原始文本: {live}")
            encoded_text = base64.b64encode(live.encode('utf-8')).decode('ascii')
            logger.debug(f"编码后文本(Base64): {encoded_text}")
            if online:
                bat_text = f"python send_qq.py -t {encoded_text} -p {pic_url} -a 1"
            else:
                bat_text = f"python send_qq.py -t {encoded_text} -p {pic_url} -a 0"

            process = await asyncio.create_subprocess_shell(f'start /wait cmd /c {bat_text}',shell=True)
            logger.info(f"执行命令: {bat_text}")
            return_code = await process.wait()
            return_code = process.returncode
            if return_code == 0:
                logger.info("命令执行成功")
            else:
                logger.error(f"命令执行失败，返回码: {return_code}")

async def main_loop():
    """主事件循环"""
    logger.debug("启动主事件循环")
    while True:
        try:
            await bilibili_live.process_live_info()
        except Exception as e:
            logger.error(f"发生错误: {e}")
        logger.info("等待10秒")
        await asyncio.sleep(10)

if __name__ == "__main__":
    bilibili_live = BilibiliLive()
    logger.debug(f"创建全局实例{bilibili_live}")
    asyncio.run(main_loop())