import logging
from logging.handlers import TimedRotatingFileHandler
from time import sleep
from bilibili_api import Credential, sync
from bilibili_api.live import LiveRoom
import requests
import win32con
import win32gui
import win32com.client
import win32clipboard
from PIL import Image
import os
import json
import io

# 创建日志文件夹
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 自定义日志文件名生成规则
def custom_namer(default_name):
    base, ext = os.path.splitext(default_name)
    if ext == ".log" and "_" not in base:
        date_part = base.split(".")[-1]
        return f"{base.split('.')[0]}_{date_part}{ext}"
    return default_name

# 配置日志格式
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 配置文件日志处理器
file_handler = TimedRotatingFileHandler(
    filename=os.path.join(log_dir, "bot.log"),  # 基础文件名
    when="midnight",       # 每天午夜切割
    interval=1,            # 每天生成一个新文件
    backupCount=0,         # 0表示保留所有历史文件
    encoding='utf-8'
)
file_handler.namer = custom_namer      # 注入自定义文件名生成器
file_handler.suffix = "%Y-%m-%d"       # 指定日期格式
file_handler.setFormatter(log_formatter)

# 控制台日志处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# 全局日志配置
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

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
        logging.info("下播")
        live = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{romm_id}"
    elif new_live_info == "0" :
        live = f"未开播"
    elif new_live_info != "0" and old_live_info == new_live_info :
        live = f"开播中"
    else:
        pic_url = new_info["room_info"]["cover"]
        logging.info("上播")
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
            win32gui.SetForegroundWindow(handle)  # 将窗口设置为前台
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

while True:
    try:
        sync(test())
    except Exception as e:
        logging.error(f"发生错误: {e}")
    logging.info(f"等待10秒")
    sleep(10)
