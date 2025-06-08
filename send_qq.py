from time import sleep
import requests
import win32con
import win32gui
import win32clipboard
import win32com.client
from PIL import Image
import json
import io
import sys
import argparse

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='发送消息至qq窗口的脚本模块')
    parser.add_argument('-p', '--pic', dest='pic_path', type=str, default=None,
                        help='传入图片的本地路径_default=None')
    parser.add_argument('-t', '--text', dest='text', type=str, default=None,
                        help='传入需要发送的内容_must')
    return parser.parse_args()

args = parse_args()
pic = args.pic_path
# 对文本参数进行反转义处理
if args.text:
    # 先还原转义序列，再解码
    text = args.text.encode('utf-8').decode('unicode_escape')
else:
    text = None

if text is None:
    print("【error】请使用-t参数传入需要发送的内容")
    sys.exit(1)


# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

handle_list= list(config['bot']['handle_list'])
at_all = bool(config['bot']['at_all'])
if pic != None :
    #下载图片
    response = requests.get(pic, stream=True)
    response.raise_for_status()
    filename = pic.split("/")[-1]
    with open(filename, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    
for handles in handle_list:
    # 动态推送到QQ
    shell = win32com.client.Dispatch("WScript.Shell")  # 初始化Shell对象用于发送按键
    handle = win32gui.FindWindow(None, handles) #  获取窗口句柄
    win32gui.ShowWindow(handle, win32con.SW_RESTORE)  # 恢复窗口（如果处于最小化状态）
    shell.SendKeys('%')  # 发送Alt键绕过Windows的前台权限限制
    win32gui.ShowWindow(handle, win32con.SW_SHOW)  # 确保窗口显示在最前端
    print(f"【info】找到窗口句柄: {handle}")
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
        sleep(2)
    #  处理文本
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
    print("【info】消息发送成功")
    sleep(2)

exit(0)