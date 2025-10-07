import asyncio
from bilibili_api import Credential, user
from bilibili_api.live import LiveRoom
from logger import setup_logger
import base64
import json

logger = setup_logger(filename='app')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

class BilibiliApp:
    def __init__(self):
        # 动态数据
        self.new_dy_data = None
        self.old_dy_data = None
        # 直播数据
        self.new_live_data = None
        self.old_live_data = None

    async def get_max_timestamp_id(self, date):
        """获取最大时间戳和对应的ID"""
        max_timestamp = int(0)
        max_id = None
        list_data = date["items"]
        for index, item in enumerate(list_data):
            timestamp = item["modules"]["module_author"]["pub_ts"]
            if timestamp > max_timestamp:
                max_timestamp = timestamp
                max_id = index
        return max_timestamp, max_id

    async def send_qq(self, bat_text):
        """发送QQ消息"""
        logger.info(f"开始执行命令: {bat_text}")
        try:
            process = await asyncio.create_subprocess_shell(f'start /wait cmd /c {bat_text}',shell=True)
            return_code = await process.wait()
            if return_code == 0:
                logger.info("命令执行成功")
            else:
                logger.error(f"命令执行失败，返回码: {return_code}")
        except Exception as e:
            logger.error(f"命令执行异常: {e}")

    async def get_dynamics(self):
        """获取动态数据"""
        user_obj = user.User(
            uid=config['bot']['uid'], 
            credential=Credential(sessdata=config['bot']['sessdata'])
        )
        return await user_obj.get_dynamics_new()

    async def process_dynamics(self):
        """处理动态数据"""
        dy_dict = await self.get_dynamics()
        
        # 初始化数据
        if self.new_dy_data is None:
            self.new_dy_data = dy_dict
            self.old_dy_data = dy_dict
        
        # 更新数据
        self.old_dy_data = self.new_dy_data
        self.new_dy_data = dy_dict

        new_maxts, new_maxid = await self.get_max_timestamp_id(self.new_dy_data)
        old_maxts, old_maxid = await self.get_max_timestamp_id(self.old_dy_data)

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

        if go and "DYNAMIC_TYPE_FORWARD" in self.new_dy_data["items"][id]["type"]:
            if "DYNAMIC_TYPE_AV" in self.new_dy_data["items"][id]["orig"]["type"]:
                forward_av = True
            else:
                forward_dy = True
        elif go and "live_rcmd" in self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]:
            go = False
            logger.info("直播推荐动态，跳过处理")

        if forward_dy and go:
            name = self.new_dy_data["items"][0]["modules"]["module_author"]["name"]
            title = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = self.new_dy_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(self.new_dy_data["items"][id]["id_str"][2:])
            other_url = self.new_dy_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【转发动态通知】\n{name}转发了{name2}的动态\n{title}\n动态地址:{url}\n原动态地址:{other_url}"
            logger.info("有转发")
        elif forward_av and go:
            name = self.new_dy_data["items"][0]["modules"]["module_author"]["name"]
            title = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = self.new_dy_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(self.new_dy_data["items"][id]["id_str"][2:])
            other_url = self.new_dy_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【转发视频通知】\n{name}转发了{name2}的视频\n{title}\n动态地址:{url}\n原视频地址:{other_url}"
            logger.info("有转发")
        elif "jump_url" in self.new_dy_data["items"][id]["basic"] and go:
            name = self.new_dy_data["items"][0]["modules"]["module_author"]["name"]
            title = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["title"] or None
            content = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"] or None
            url = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【动态通知】\n【{name}】发布了新动态\n{title}\n{content}\n动态地址:{url}"
            logger.info("有新动态")
        elif go:
            name = self.new_dy_data["items"][0]["modules"]["module_author"]["name"]
            tab = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"] or None
            title = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["title"] or None
            pic_url = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["cover"]
            url = self.new_dy_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【视频通知】\n【{name}】更新了新视频\n{tab}\n《{title}》\n视频地址:{url}"
            logger.info("有新视频")

        if go:
            return text, pic_url
        else:
            return None, None

    async def get_room_info(self):
        """获取直播间信息"""
        room = LiveRoom(
            credential=Credential(sessdata=config['live']['sessdata']), 
            room_display_id=config['live']['room_display_id'])
        return await room.get_room_info()

    async def process_live_info(self):
        """处理直播间信息"""
        live_dict = await self.get_room_info()
        
        # 初始化数据
        if self.new_live_data is None:
            self.new_live_data = live_dict
            self.old_live_data = live_dict
        
        # 更新数据
        self.old_live_data = self.new_live_data
        self.new_live_data = live_dict

        new_live_info = str(self.new_live_data["room_info"]["live_start_time"])
        old_live_info = str(self.old_live_data["room_info"]["live_start_time"])
        title = self.new_live_data["room_info"]["title"]
        name = self.new_live_data["anchor_info"]["base_info"]["uname"]
        room_id = self.new_live_data["room_info"]["room_id"]
        pic_url = None
        live_msg = None
        online = False

        if new_live_info == "0" and old_live_info != "0":
            pic_url = self.new_live_data["room_info"]["cover"]
            logger.info("下播")
            live_msg = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"
        elif new_live_info == "0":
            live_msg = f"未开播"
        elif new_live_info != "0" and old_live_info == new_live_info:
            live_msg = f"开播中"
        else:
            pic_url = self.new_live_data["room_info"]["cover"]
            logger.info("上播")
            online = True
            live_msg = f"\n【直播通知】\n{name}开播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"

        if pic_url is not None:
            return online, live_msg, pic_url
        else:
            return None, None, None

    async def run(self):
        """主函数，获取直播间信息和动态信息并处理"""
        tasks = [
            asyncio.create_task(self.process_live_info()),
            asyncio.create_task(self.process_dynamics())
        ]
        results = await asyncio.gather(*tasks)

        live_data = results[0]
        bot_data = results[1]

        live_online, live_msg, live_pic = live_data
        dy_msg, dy_pic = bot_data

        if live_msg is not None:
            encoded_text = base64.b64encode(live_msg.encode('utf-8')).decode('ascii')
            if live_online is True:
                bat_text = f'python send_qq.py -t "{encoded_text}" -p {live_pic} -a 1'
            elif live_online is False:
                bat_text = f'python send_qq.py -t "{encoded_text}" -p {live_pic} -a 0'
            await self.send_qq(bat_text)

        if dy_msg is not None:
            if dy_pic is None:
                encoded_text = base64.b64encode(dy_msg.encode('utf-8')).decode('ascii')
                bat_text = f"python send_qq.py -t {encoded_text} -a 1"
            else:
                encoded_text = base64.b64encode(dy_msg.encode('utf-8')).decode('ascii')
                bat_text = f"python send_qq.py -t {encoded_text} -p {dy_pic} -a 1"
            await self.send_qq(bat_text)

# 创建全局实例
app = BilibiliApp()

async def main():
    """主函数"""
    await app.run()

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