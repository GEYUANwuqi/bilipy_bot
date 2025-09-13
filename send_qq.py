from time import sleep
import requests
import win32con
import win32gui
import win32clipboard
import win32com.client
import win32api
from PIL import Image
import json
import io
import sys
import argparse
from logger import setup_logger
from typing import Union

logger = setup_logger(filename='send_qq')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='发送消息至qq窗口的脚本模块')
    parser.add_argument('-p', '--pic', dest='pic_path', type=str, default=None,
                        help='传入图片的本地路径_default=None')
    parser.add_argument('-t', '--text', dest='text', type=str, default=None,
                        help='传入需要发送的内容_must')
    parser.add_argument('-a', '--at_all', dest='at_all', type=int, default=1,
                        help='是否强制@所有人，0为强制否，其他参数代表config为最高优先级_default=1')
    return parser.parse_args()

def send_to_window_ntqq(hwnd:int, text:str, at_all=False, pic_path=None,sleep_time:Union[int,float]=2):
    """向指定NTQQ窗口发送消息（文本 + @全体）"""
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # 恢复窗口
    win32gui.SetForegroundWindow(hwnd)  # 确保窗口在前台
    sleep(sleep_time)

    # @全体
    if at_all:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, "@")
        win32clipboard.CloseClipboard()
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # 按下Ctrl
        win32api.keybd_event(ord('V'), 0, 0, 0)  # 按下V
        win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)  # 释放V
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        sleep(sleep_time)   #等待@符号加载
        # 按下Enter键
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        # 释放Enter键
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        sleep(sleep_time)

    # 文本
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    win32clipboard.CloseClipboard()
    sleep(sleep_time)

    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # 按下Ctrl
    win32api.keybd_event(ord('V'), 0, 0, 0)  # 按下V
    win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)  # 释放V
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

    # 处理图片
    if pic_path is not None:
        # 下载图片
        response = requests.get(pic_path, stream=True)
        response.raise_for_status()
        filename = pic_path.split("/")[-1]
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        # 发送图片
        image = Image.open(filename)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()
        sleep(sleep_time)
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # 按下Ctrl
        win32api.keybd_event(ord('V'), 0, 0, 0)  # 按下V
        win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)  # 释放V
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

    # 发送
    sleep(sleep_time)
    # 按下Enter键
    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
    # 释放Enter键
    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
    sleep(sleep_time)
    print(f"✅ 已向窗口[{win32gui.GetWindowText(hwnd)}]发送消息")

def enum_target_windows_ntqq(target_titles:list):
    """枚举NTQQ目标窗口（严格匹配标题）"""
    result = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title in target_titles:  # 精确匹配
                result.append(hwnd)
        return True
    win32gui.EnumWindows(callback, None)
    return result

def send_to_window_qq(handle:int, text:str, at_all=False, pic_path=None, sleep_time:Union[int,float]=2):
    """向指定传统QQ窗口发送消息（文本 + @全体）"""
    # 初始化Shell对象用于发送按键
    shell = win32com.client.Dispatch("WScript.Shell")
    win32gui.ShowWindow(handle, win32con.SW_RESTORE)  # 恢复窗口（如果处于最小化状态）
    shell.SendKeys('%')  # 发送Alt键绕过Windows的前台权限限制
    win32gui.ShowWindow(handle, win32con.SW_SHOW)  # 确保窗口显示在最前端
    logger.info(f"找到窗口句柄: {handle}")
    
    if at_all:
        # 处理@符号
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, "@")
        win32clipboard.CloseClipboard()
        win32gui.SendMessage(handle, 770, 0, 0)  # Ctrl+V
        sleep(sleep_time)   # 等待@符号加载
        win32gui.SendMessage(handle, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        sleep(sleep_time)
    
    # 处理文本
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    win32clipboard.CloseClipboard()
    sleep(sleep_time)
    win32gui.SendMessage(handle, 770, 0, 0)  # Ctrl+V
    
    # 处理图片
    if pic_path is not None:
        # 下载图片
        response = requests.get(pic_path, stream=True)
        response.raise_for_status()
        filename = pic_path.split("/")[-1]
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                
        # 发送图片
        image = Image.open(filename)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()
        sleep(sleep_time)
        win32gui.SendMessage(handle, 770, 0, 0)  # Ctrl+V
    
    # 发送
    sleep(sleep_time)
    win32gui.SendMessage(handle, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
    logger.info("消息发送成功")
    sleep(sleep_time)

args = parse_args()
pic = args.pic_path
at_all_must = args.at_all
# 对文本参数进行反转义处理
if args.text:
    # 先还原转义序列，再解码
    text = args.text.encode('utf-8').decode('unicode_escape')
else:
    text = None

if text is None:
    logger.error("请使用-t参数传入需要发送的内容")
    sys.exit(1)


# 从配置文件中读取配置
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)

sleep_time = config.get('sleep_time')

handle_list= list(config['bot']['handle_list'])
if at_all_must == 0:
    at_all = False
else:
    at_all = bool(config['bot']['at_all'])

# 检查是否使用NTQQ模式
is_ntqq = bool(config.get('ntqq', False))

if is_ntqq:
    # NTQQ模式
    hwnds = enum_target_windows_ntqq(handle_list)
    if not hwnds:
        print("❌ 未找到符合条件的窗口")
        sys.exit(1)
    else:
        print(f"找到 {len(hwnds)} 个目标窗口")
        for hwnd in hwnds:
            send_to_window_ntqq(hwnd, text, at_all, pic,sleep_time)
else:
    # 传统QQ模式
    for handles in handle_list:
        handle = win32gui.FindWindow(None, handles) # 获取窗口句柄
        if handle != 0:  # 确保窗口存在
            send_to_window_qq(handle, text, at_all, pic,sleep_time)
        else:
            logger.warning(f"未找到窗口: {handles}")

exit(0)