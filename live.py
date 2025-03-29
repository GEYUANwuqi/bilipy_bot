import logging
from logging.handlers import TimedRotatingFileHandler
from time import sleep
from bilibili_api import Credential, sync
from bilibili_api.live import LiveRoom
import requests
import win32con
import win32gui
import win32clipboard
import win32com.client
from PIL import Image
import os
import sys
import json
import io

LOG_DIR = "logs"  # 日志目录名
os.makedirs(LOG_DIR, exist_ok=True)  # 自动创建目录

class WorkerLogHandler(TimedRotatingFileHandler):
    """子进程专用日志处理器"""
    def __init__(self, worker_name):
        filename = os.path.join(LOG_DIR, f"{worker_name}.log")
        super().__init__(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=14,  # 子进程日志保留14天
            encoding="utf-8"
        )
        self.suffix = "%Y-%m-%d"
        self.namer = self._custom_namer

    @staticmethod
    def _custom_namer(default_name):
        base, ext = os.path.splitext(default_name)
        parts = base.split(".")
        if len(parts) > 1 and parts[-1].isdigit():
            return f"{'.'.join(parts[:-1])}_{parts[-1]}{ext}"
        return default_name

def setup_worker_logger():
    # 获取工作进程名称
    worker_name = "live"
    try:
        idx = sys.argv.index("--name")
        worker_name = sys.argv[idx+1]
    except (ValueError, IndexError):
        pass

    logger = logging.getLogger(f"Worker.{worker_name}")
    logger.setLevel(logging.INFO)

    # 文件处理器（带滚动）
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, f"{worker_name}.log"),
        when="midnight",
        backupCount=3
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()

    # 差异化格式
    file_formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "[%(levelname)s][%(name)s] %(message)s"
    )

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_worker_logger()  # 默认日志配置

# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

async def test():
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
    
    if pic_url != None:
        #下载图片
        response = requests.get(pic_url, stream=True)
        response.raise_for_status()
        filename = pic_url.split("/")[-1]
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                
    handle_list= list(config['live']['handle_list'])
    at_all = bool(config['live']['at_all'])

    if pic_url != None:
        for handles in handle_list:
            # 动态推送到QQ
            shell = win32com.client.Dispatch("WScript.Shell")  # 初始化Shell对象用于发送按键
            handle = win32gui.FindWindow(None, handles) #  获取窗口句柄
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)  # 恢复窗口（如果处于最小化状态）
            shell.SendKeys('%')  # 发送Alt键绕过Windows的前台权限限制
            win32gui.ShowWindow(handle, win32con.SW_SHOW)  # 确保窗口显示在最前端
            logging.info(f"找到窗口句柄: {handle}")

            if online and at_all :
                #  处理@符号
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, "@")
                win32clipboard.CloseClipboard()
                sleep(2)
                #
                win32gui.SendMessage(handle, 770, 0, 0)  #cv
                sleep(2)   #等待@符号加载
                win32gui.SendMessage(handle, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

            #  处理文本
            sleep(2)
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, live)
            win32clipboard.CloseClipboard()
            sleep(2)
            win32gui.SendMessage(handle, 770, 0, 0)  #cv
            if pic_url != None:
                #  处理图片
                image = Image.open(filename)
                output = io.BytesIO()
                image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                #  
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)
                win32clipboard.CloseClipboard()
                sleep(2)
                #
                win32gui.SendMessage(handle, 770, 0, 0)  #cv
            # 发送
            sleep(2)
            win32gui.SendMessage(handle, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            sleep(2)

if __name__ == "__main__":
    while True:
        try:
            sync(test())
        except Exception as e:
            logger.error(f"发生错误: {e}")
        logger.info(f"等待10秒")
        sleep(10)
