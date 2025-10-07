import asyncio
import base64
import json
from bilibili_api import Credential,user
from logger import setup_logger

logger = setup_logger(filename='bot')

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    configs:dict = json.load(config_file)

config = configs.get("bot",{})
if not config:
    logger.error("未在config.json内找到bot配置")
    raise SystemExit(1)

class BilibiliBot:
    def __init__(self):
        self.new_data = None
        self.old_data = None

    async def get_dynamics(self):
        """获取动态数据"""
        credential_uid = Credential(sessdata=config['sessdata'])
        dy_dict = await user.User.get_dynamics_new(
            self=user.User(uid=config['uid'], credential=credential_uid))
        return dy_dict

    def get_max_timestamp_id(self, date):
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

    async def process_dynamics(self):
        """处理动态数据并发送通知"""
        dy_dict = await self.get_dynamics()
        
        # 初始化数据
        if self.new_data is None:
            self.new_data = dy_dict
            self.old_data = dy_dict
            logger.debug(f"初始化数据{self.new_data}")
        
        # 更新数据
        self.old_data = self.new_data
        self.new_data = dy_dict

        name = self.new_data["items"][0]["modules"]["module_author"]["name"]
        id = int(0)

        new_maxts, new_maxid = self.get_max_timestamp_id(self.new_data)
        old_maxts, old_maxid = self.get_max_timestamp_id(self.old_data)
        go = False
        forward_dy = False
        forward_av = False
        pic = None
        
        if new_maxts > old_maxts:
            logger.debug(f"新动态数据: {new_maxts},{new_maxid}, 旧动态数据: {old_maxts},{old_maxid}")
            logger.info(f"最大的时间戳是: {new_maxts}, 对应的ID是: {new_maxid}")
            go = True
            id = new_maxid
            
        if "DYNAMIC_TYPE_FORWARD" in self.new_data["items"][id]["type"]:
            logger.debug("检测到DYNAMIC_TYPE_FORWARD")
            if "DYNAMIC_TYPE_AV" in self.new_data["items"][id]["orig"]["type"]:
                forward_av = True
                logger.debug("检测到DYNAMIC_TYPE_AV")
            else:
                forward_dy = True
                logger.debug("默认处理为转发动态")
        elif "live_rcmd" in self.new_data["items"][id]["modules"]["module_dynamic"]["major"]:
            go = False
            logger.info("直播推荐动态，跳过处理")

        if forward_dy and go:
            title = self.new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = self.new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(self.new_data["items"][id]["id_str"][2:])
            other_url = self.new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【转发动态通知】\n{name}转发了{name2}的动态\n{title}\n动态地址:{url}\n原动态地址:{other_url}"
            logger.info("有转发")
        elif forward_av and go:
            title = self.new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
            name2 = self.new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
            url = "www.bilibili.com/opus/" + str(self.new_data["items"][id]["id_str"][2:])
            other_url = self.new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【转发视频通知】\n{name}转发了{name2}的视频\n{title}\n动态地址:{url}\n原视频地址:{other_url}"
            logger.info("有转发")
        elif "jump_url" in self.new_data["items"][id]["basic"] and go:
            title = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["title"] or None
            content = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"] or None
            url = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
            text = f"\n【动态通知】\n【{name}】发布了新动态\n{title}\n{content}\n动态地址:{url}"
            logger.info("有新动态")
        elif go:
            tab = self.new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"] or None
            title = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["title"] or None
            pic = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["cover"]
            url = self.new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
            text = f"\n【视频通知】\n【{name}】更新了新视频\n{tab}\n《{title}》\n视频地址:{url}"
            logger.info("有新视频")

        if go:
            encoded_text = base64.b64encode(text.encode('utf-8')).decode('ascii')

            if pic is None:
                bat_text = f"python send_qq.py -t {encoded_text} -a 1"
            else:
                bat_text = f"python send_qq.py -t {encoded_text} -p {pic} -a 1"

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
            await bilibili_bot.process_dynamics()
        except Exception as e:
            logger.error(f"发生错误: {e}")
        logger.info("等待10秒")
        await asyncio.sleep(10)

if __name__ == "__main__":
    bilibili_bot = BilibiliBot()
    logger.debug(f"创建全局实例{bilibili_bot}")
    asyncio.run(main_loop())