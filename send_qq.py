import argparse
import json
import io
import os
import glob
import time
import requests
import win32gui
import win32con
import win32clipboard
import win32api
from PIL import Image
import re
import logging

# ------------------ Logger ------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("send_qq")

# ------------------ 命令行参数 ------------------
parser = argparse.ArgumentParser(description='发送消息到QQ窗口')
parser.add_argument('-t', '--text', required=True, help='发送的文本内容')
parser.add_argument('-p', '--pic', default=None, help='图片URL或本地路径')
parser.add_argument('-c', '--config_type', default='live', choices=['bot','live'], help='配置段')
parser.add_argument('--mode', choices=['start','stop'], default='start', help='开播/下播模式')
args = parser.parse_args()

# ------------------ 配置文件读取 ------------------
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

cfg = config[args.config_type]
handle_list = cfg.get("handle_list", [])
class_list = cfg.get("class_list", [])
sleep_config = cfg.get("sleep_config", {"window_activate":0.2,"paste":0.2,"enter":0.2,"loop":1})
config_at_all = bool(cfg.get("at_all", False))

# ------------------ 决定最终 @全体 ------------------
final_at_all = config_at_all
logger.info(f"使用配置文件 @全体设置: {final_at_all}")
logger.info(f"匹配窗口列表: {handle_list}, 类名: {class_list}, @所有人: {final_at_all}")

# ------------------ 文本解析 ------------------
def decode_unicode_escapes(text):
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1),16)), text)
    text = text.replace("\\n", "\n")
    return text.strip('"')

text = decode_unicode_escapes(args.text)
logger.info(f"最终发送文本:\n{text}")

# ------------------ 下载图片 ------------------
filename = None
if args.pic:
    try:
        if args.pic.startswith("http"):
            url_filename = args.pic.split("/")[-1]
            if not url_filename.lower().endswith('.jpg'):
                url_filename += ".jpg"
            response = requests.get(args.pic, stream=True)
            response.raise_for_status()
            filename = url_filename
            with open(filename,'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            logger.info(f"图片下载成功: {filename}")
        else:
            filename = args.pic  # 本地路径
            logger.info(f"使用本地图片: {filename}")
    except Exception as e:
        logger.error(f"图片获取失败: {e}")
        filename = None

# ------------------ 清理旧图片 ------------------
def cleanup_old_images(keep_filename=None):
    jpg_files = glob.glob("*.jpg")
    for file in jpg_files:
        if keep_filename and file == keep_filename:
            continue
        try:
            os.remove(file)
            logger.info(f"已清理旧图片: {file}")
        except Exception as e:
            logger.error(f"清理图片 {file} 失败: {e}")

# ------------------ 窗口匹配 ------------------
def enum_windows_callback(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        hwnds.append((hwnd, title, cls))

def find_target_windows(target_names, class_names):
    hwnds = []
    win32gui.EnumWindows(enum_windows_callback, hwnds)
    matched = []
    for hwnd, title, cls in hwnds:
        if cls not in class_names:
            continue
        for name in target_names:
            if name in title:
                matched.append((hwnd, title, cls))
                break
    return matched

matched_windows = find_target_windows(handle_list, class_list)
if not matched_windows:
    logger.error("没有找到匹配的QQ聊天窗口")
    exit(1)
logger.info(f"找到 {len(matched_windows)} 个匹配窗口")

# ------------------ 前台发送 ------------------
def activate_window(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(sleep_config["window_activate"])

def paste_text(hwnd, text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    win32clipboard.CloseClipboard()
    activate_window(hwnd)
    win32api.keybd_event(win32con.VK_CONTROL,0,0,0)
    win32api.keybd_event(ord('V'),0,0,0)
    win32api.keybd_event(ord('V'),0,win32con.KEYEVENTF_KEYUP,0)
    win32api.keybd_event(win32con.VK_CONTROL,0,win32con.KEYEVENTF_KEYUP,0)
    time.sleep(sleep_config["paste"])

def paste_image(hwnd, filename):
    try:
        image = Image.open(filename)
        output = io.BytesIO()
        image.convert("RGB").save(output,"BMP")
        data = output.getvalue()[14:]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB,data)
        win32clipboard.CloseClipboard()
        activate_window(hwnd)
        win32api.keybd_event(win32con.VK_CONTROL,0,0,0)
        win32api.keybd_event(ord('V'),0,0,0)
        win32api.keybd_event(ord('V'),0,win32con.KEYEVENTF_KEYUP,0)
        win32api.keybd_event(win32con.VK_CONTROL,0,win32con.KEYEVENTF_KEYUP,0)
        time.sleep(sleep_config["paste"])
    except Exception as e:
        logger.error(f"图片处理失败: {e}")

def send_enter(hwnd):
    activate_window(hwnd)
    win32api.keybd_event(win32con.VK_RETURN,0,0,0)
    win32api.keybd_event(win32con.VK_RETURN,0,win32con.KEYEVENTF_KEYUP,0)
    time.sleep(sleep_config["enter"])

# ------------------ 主流程 ------------------
try:
    for hwnd, title, cls in matched_windows:
        logger.info(f"处理窗口: {title} (类名: {cls}, 句柄: {hwnd})")
        if final_at_all:
            paste_text(hwnd, "@所有人")
            send_enter(hwnd)
        paste_text(hwnd, text)
        if filename:
            paste_image(hwnd, filename)
        send_enter(hwnd)
        logger.info(f"消息已发送到窗口: {title}")
        time.sleep(sleep_config["loop"])
except Exception as e:
    logger.error(f"发送过程中出现错误: {e}")
finally:
    cleanup_old_images(filename)
    if filename:
        logger.info(f"新图片 {filename} 已被保留")
