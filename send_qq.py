import argparse
import json
import os
import io
import time
import requests
import win32gui
import win32con
import win32clipboard
import win32api
from PIL import Image
import re
import logging
import glob

# ------------------ Logger ------------------
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("send_qq")

# ------------------ 命令行参数 ------------------
parser = argparse.ArgumentParser(description="发送消息到QQ窗口")
parser.add_argument('-t', '--text', required=True, help="发送的文本内容")
parser.add_argument('-p', '--pic', default=None, help="图片URL")
parser.add_argument('-c', '--config_type', default="live", choices=["bot","live"], help="配置段：bot/live")
parser.add_argument('-a', '--at_all', type=int, choices=[0, 1], help="是否@全体成员 (0:否, 1:是)", default=None)
parser.add_argument('--dry-run', action='store_true', help="只调试不实际发送")
args = parser.parse_args()

# ------------------ 配置读取 ------------------
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

cfg = config[args.config_type]
handle_list = cfg.get("handle_list", [])
class_list = cfg.get("class_list", ["TXGuiFoundation", "Chrome_WidgetWin_1"])
config_at_all = bool(cfg.get("at_all", False))
sleep_config = cfg.get("sleep_config", {})
ntqq = config.get("ntqq", False)  # 全局QQNT设置
sleep_time = config.get("sleep_time", 2)  # 全局延迟设置

# 从sleep_config中获取具体延迟时间，如果没有则使用默认值
window_activate_delay = sleep_config.get("window_activate", 0.2)
paste_delay = sleep_config.get("paste", 0.2)
enter_delay = sleep_config.get("enter", 0.2)
loop_delay = sleep_config.get("loop", 1)

if args.at_all is not None:
    final_at_all = bool(args.at_all)
else:
    final_at_all = config_at_all

logger.info(f"匹配窗口列表: {handle_list}, 类名列表: {class_list}, @所有人: {final_at_all}, QQNT模式: {ntqq}")
logger.info(f"延迟配置: 激活{window_activate_delay}s, 粘贴{paste_delay}s, 回车{enter_delay}s, 循环{loop_delay}s")

# ------------------ 文本解析 ------------------
def decode_unicode_escapes(text):
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1),16)), text)
    text = text.replace("\\n", "\n")
    text = text.strip('"')
    return text

text = decode_unicode_escapes(args.text)
logger.info(f"最终发送文本:\n{text}")

# ------------------ 下载图片 ------------------
filename = None
if args.pic:
    try:
        # 从URL中提取文件名
        url_parts = args.pic.split("/")
        url_filename = url_parts[-1] if url_parts[-1] else url_parts[-2]
        
        # 确保有.jpg扩展名
        if not url_filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            url_filename += ".jpg"
            
        response = requests.get(args.pic, stream=True)
        response.raise_for_status()
        filename = url_filename
        with open(filename, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        logger.info(f"图片下载成功: {filename}")
    except Exception as e:
        logger.error(f"图片下载失败: {e}")
        filename = None

# ------------------ 窗口匹配 ------------------
def enum_windows_callback(hwnd, hwnds):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        hwnds.append((hwnd, title, cls))

def find_target_windows(target_names, target_classes):
    hwnds = []
    win32gui.EnumWindows(enum_windows_callback, hwnds)
    matched = []
    for hwnd, title, cls in hwnds:
        if cls not in target_classes:
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

# ------------------ 激活窗口 ------------------
def activate_window(hwnd, cls, is_ntqq):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        if is_ntqq or cls == "Chrome_WidgetWin_1":
            # QQNT 或配置为QQNT模式的窗口使用前台激活
            win32gui.SetForegroundWindow(hwnd)
            logger.info(f"使用前台激活模式 (QQNT/Chrome窗口)")
        else:
            # 旧版QQ使用后台模式
            logger.info(f"使用后台模式 (旧版QQ)")
        time.sleep(window_activate_delay)
        return True
    except Exception as e:
        logger.error(f"窗口激活失败: {e}")
        return False

# ------------------ 粘贴和发送 ------------------
def paste_text_to_window(hwnd, text, is_ntqq):
    """粘贴文本到窗口，根据模式选择前台或后台粘贴"""
    try:
        # 设置剪贴板
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
        
        if is_ntqq:
            # QQNT模式：前台粘贴
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x56, 0, 0, 0)  # V
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # 旧版QQ模式：后台发送消息
            win32gui.SendMessage(hwnd, win32con.WM_PASTE, 0, 0)
        
        time.sleep(paste_delay)
        return True
    except Exception as e:
        logger.error(f"文本粘贴失败: {e}")
        return False

def paste_image_to_window(hwnd, filename, is_ntqq):
    """粘贴图片到窗口，根据模式选择前台或后台粘贴"""
    try:
        image = Image.open(filename)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # 去除BMP头
        
        # 设置剪贴板
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()
        
        if is_ntqq:
            # QQNT模式：前台粘贴
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x56, 0, 0, 0)  # V
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # 旧版QQ模式：后台发送消息
            win32gui.SendMessage(hwnd, win32con.WM_PASTE, 0, 0)
        
        time.sleep(paste_delay)
        return True
    except Exception as e:
        logger.error(f"图片粘贴失败: {e}")
        return False

def send_enter_to_window(hwnd, is_ntqq):
    """发送回车键，根据模式选择前台或后台发送"""
    try:
        if is_ntqq:
            # QQNT模式：前台发送
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # 旧版QQ模式：后台发送回车
            win32gui.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            win32gui.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        
        time.sleep(enter_delay)
        return True
    except Exception as e:
        logger.error(f"发送回车失败: {e}")
        return False

# ------------------ 清理旧图片 ------------------
def cleanup_old_images(keep_filename=None):
    """清理旧的图片文件，保留当前使用的文件"""
    image_extensions = ('*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp')
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(ext))
    
    for file in image_files:
        if keep_filename and file == keep_filename:
            continue
        try:
            os.remove(file)
            logger.info(f"已清理旧图片: {file}")
        except Exception as e:
            logger.debug(f"清理文件失败 {file}: {e}")

# ------------------ 主流程 ------------------
try:
    for hwnd, title, cls in matched_windows:
        logger.info(f"处理窗口: {title} (句柄: {hwnd}, 类名: {cls})")
        
        # 判断是否为QQNT模式
        is_ntqq_mode = ntqq or cls == "Chrome_WidgetWin_1"
        
        if not activate_window(hwnd, cls, is_ntqq_mode):
            logger.error("窗口激活失败，跳过此窗口")
            continue

        if args.dry_run:
            logger.info("Dry-run模式：跳过实际发送")
            continue

        # @全体成员
        if final_at_all:
            paste_text_to_window(hwnd, "@所有人", is_ntqq_mode)
            send_enter_to_window(hwnd, is_ntqq_mode)
            time.sleep(loop_delay)

        # 发送文本
        paste_text_to_window(hwnd, text, is_ntqq_mode)

        # 发送图片
        if filename:
            paste_image_to_window(hwnd, filename, is_ntqq_mode)

        # 最终发送
        send_enter_to_window(hwnd, is_ntqq_mode)
        logger.info(f"消息已发送到窗口: {title}")
        
        # 窗口间延迟
        time.sleep(sleep_time)

except Exception as e:
    logger.error(f"发送过程中出现错误: {e}")

finally:
    # 清理旧图片，保留当前使用的图片
    cleanup_old_images(filename)
    if filename:
        logger.info(f"新图片 {filename} 已保留")