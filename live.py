from time import sleep
from bilibili_api import Credential, sync
from bilibili_api.live import LiveRoom
import requests
import win32con
import win32gui
import win32clipboard
from PIL import Image
import os
import json
import io
import datetime

async def test():
    uid = Credential(sessdata="")
    live = await LiveRoom.get_room_info(self=LiveRoom(credential=uid, room_display_id=114514))
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
        print("下播")
        live = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{romm_id}"
    elif new_live_info == "0" :
        live = f"未开播"
    elif new_live_info != "0" and old_live_info == new_live_info :
        live = f"开播中"
    else:
        pic_url = new_info["room_info"]["cover"]
        print("上播")
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
    handle_list= ["测试","test","BOT"]
    at_all = True
    if pic_url != None:
        for list in handle_list:
            # 动态推送到QQ
            handle = win32gui.FindWindow(None, list) #  获取窗口句柄
            print(handle)
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)  # 恢复窗口
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
    sync(test())
    new_time = datetime.datetime.now()
    print(f"等待10秒,{new_time}")
    sleep(10)
