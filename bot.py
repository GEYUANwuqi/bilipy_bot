from time import sleep
from bilibili_api import Credential, sync
from bilibili_api import user
import requests
import win32con
import win32gui
import win32clipboard
from PIL import Image
import os
import json
import io
import datetime

# 检查直播的办法"live_rcmd" in new_data["items"][id]["modules"]["module_dynamic"]["major"]
# 检查置顶的办法"module_tag" in new_data["items"][id]["modules"]

async def test():

    credential_uid = Credential(sessdata="")
    
    dy_dict = await user.User.get_dynamics_new(self=user.User(uid=114514, credential=credential_uid),offset="")
    if os.path.getsize("old.json") == 0:
    # 如果 old.json 文件为空，则将数据写入 new.json 和 old.json 文件
        with open("new.json", "w", encoding="utf-8") as new_file, open("old.json", "w", encoding="utf-8") as old_file:
            json.dump(dy_dict, new_file, ensure_ascii=False, indent=4)
            json.dump(dy_dict, old_file, ensure_ascii=False, indent=4)
    else:
    # 如果 old.json 文件不为空，则将 new.json 文件的内容移动到 old.json 文件中，并将新的数据写入 new.json 文件
        with open("new.json", "r", encoding="utf-8") as new_file:
            new_data = json.load(new_file)
        with open("old.json", "w", encoding="utf-8") as old_file:
            json.dump(new_data, old_file, ensure_ascii=False, indent=4)
        with open("new.json", "w", encoding="utf-8") as new_file:
            json.dump(dy_dict, new_file, ensure_ascii=False, indent=4)
    # 读取 new.json 和 old.json 文件的内容到变量中
    with open("new.json", "r", encoding="utf-8") as new_file, open("old.json", "r", encoding="utf-8") as old_file:
        new_data = json.load(new_file)
        old_data = json.load(old_file)

    name = new_data["items"][0]["modules"]["module_author"]["name"]
    id = int(0)

    def getmax_tsid(date):
        max_timestamp = None
        max_id = None
        # 遍历items列表中的每个元素
        list = date["items"]
        for index, item in enumerate(list):
            timestamp = item["modules"]["module_author"]["pub_ts"]
            # 如果max_timestamp为None或者当前时间戳大于max_timestamp，则更新最大时间戳和对应的ID
            if max_timestamp is None or timestamp > max_timestamp:
                max_timestamp = timestamp
                max_id = index
        return max_timestamp, max_id
    
    new_maxts, new_maxid = getmax_tsid(new_data)
    old_maxts, old_maxid = getmax_tsid(old_data)
    go = False
    forward = False
    pic = None
    if new_maxts > old_maxts :
        print(f"最大的时间戳是: {new_maxts}, 对应的ID是: {new_maxid}")
        go = True
        id = new_maxid
    if "DYNAMIC_TYPE_FORWARD" in new_data["items"][id]["type"] :
        forward = True
    elif "live_rcmd" in new_data["items"][id]["modules"]["module_dynamic"]["major"] :
        go = False
    
    if forward :
        title = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"]
        name2 = new_data["items"][id]["orig"]["modules"]["module_author"]["name"]
        url =  "www.bilibili.com/opus/" + str(new_data["items"][id]["id_str"][2:])
        other_url = new_data["items"][id]["orig"]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
        text = f"\n【转发通知】\n{name}转发了{name2}的动态\n{title}\n动态地址:{url}\n原动态地址:{other_url}"
        print("有转发")
    elif "jump_url" in new_data["items"][id]["basic"] and go:
        title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["title"] or None
        content = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["summary"]["text"] or None
        url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["opus"]["jump_url"][2:]
        text = f"\n【动态通知】\n【{name}】发布了新动态\n{title}\n{content}\n动态地址:{url}"
        print("有新动态")
    elif go :
        tab = new_data["items"][id]["modules"]["module_dynamic"]["desc"]["text"] or None
        title = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["title"] or None
        pic = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["cover"]
        url = new_data["items"][id]["modules"]["module_dynamic"]["major"]["archive"]["jump_url"][2:]
        text = f"\n【视频通知】\n【{name}】更新了新视频\n{tab}\n《{title}》\n视频地址:{url}"
        print("有新视频")
    handle_list= ["测试","test","BOT"]
    at_all = True
    if go or forward :
            if pic != None :
                #下载图片
                response = requests.get(pic, stream=True)
                response.raise_for_status()
                filename = pic.split("/")[-1]
                with open(filename, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
            
            for list in handle_list:
                # 动态推送到QQ
                handle = win32gui.FindWindow(None, list) #  获取窗口句柄
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)  # 恢复窗口
                print(handle)
                if at_all:
                    #  处理@符号
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, "@")
                    win32clipboard.CloseClipboard()
                    win32gui.SendMessage(handle, 770, 0, 0)  #cv
                    #
                    sleep(2)   #等待@符号加载
                    win32gui.SendMessage(handle, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                #  处理文本
                sleep(2)
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                win32clipboard.CloseClipboard()
                sleep(2)
                win32gui.SendMessage(handle, 770, 0, 0)  #cv
                if pic != None:
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

