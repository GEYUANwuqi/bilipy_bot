import argparse
import json
import io
import time
import requests
import win32gui
import win32con
import win32clipboard
import win32api
from PIL import Image
from logger import setup_logger
from typing import Optional
import argparse
logger = setup_logger(filename='send_qq')

# 命令行解析
class ArgsType(argparse.Namespace):
    text: str
    pic: Optional[str]
    at_all: int
    dry_run: bool
parser = argparse.ArgumentParser(description="发送消息到QQ窗口")
parser.add_argument('-t', '--text', required=True, help="发送的文本内容")
parser.add_argument('-p', '--pic', default=None, help="图片URL")
parser.add_argument('-a', '--at_all', required=True, type=int, choices=[0,1], help="是否@全体成员 (0:否 1:是)")
parser.add_argument('--dry-run', action='store_true', help="只调试不实际发送")
args = parser.parse_args(namespace=ArgsType())
logger.debug(f"命令行参数: {args}")

# 参数解析
with open("config.json", "r", encoding="utf-8") as f:
    config:dict = json.load(f)
config:dict = config.get("send_qq") # type:ignore

sleep_time:int = config.get("sleep_time") # type:ignore
if args.at_all == 1 :
    final_at_all = True
    logger.debug("因命令行参数开启@全体成员")
else :
    final_at_all = False
    logger.debug("因命令行参数关闭@全体成员")

if config.get("auto"):
    class_list = ["TXGuiFoundation", "Chrome_WidgetWin_1"]
    pattern = "自动模式"
    logger.debug("自动模式: 同时匹配TXGuiFoundation和Chrome_WidgetWin_1")
elif config.get("ntqq"):
    class_list = ["Chrome_WidgetWin_1"]
    pattern = "QQNT模式"
    logger.debug("QQNT模式: 匹配Chrome_WidgetWin_1")
else:
    class_list = ["TXGuiFoundation"]
    pattern = "旧版QQ模式"
    logger.debug("旧版QQ模式: 匹配TXGuiFoundation")

handle_list = config.get("handle_list")
logger.info(f"匹配窗口列表: {handle_list}, 类名列表: {class_list}, @所有人: {final_at_all}, 窗口匹配模式: {pattern}")

# 文本解析
# 对文本参数进行反转义处理
# 先还原转义序列，再解码
logger.debug(f"原始文本: {args.text}")
text = args.text.encode('utf-8').decode('unicode_escape')
logger.info(f"发送文本:\n{text}")

# 存入图片
image_data = None
if args.pic:
    logger.debug(f"图片URL: {args.pic}")
    logger.info("尝试进行图片下载")
    try:
        response = requests.get(args.pic, stream=True)
        response.raise_for_status()
        image_data = io.BytesIO(response.content)
        logger.info("图片下载成功并保存到内存")
    except Exception as e:
        logger.error(f"图片下载失败: {e}")

# ------------------ 窗口匹配 ------------------
def enum_windows_callback(hwnd, hwnds:list):
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
        logger.info(f"活动窗口: {cls} - {title}")
        if is_ntqq :
            # QQNT 或配置为QQNT模式的窗口使用前台激活
            win32gui.SetForegroundWindow(hwnd)
            logger.info(f"前台激活{hwnd} (QQNT/Chrome窗口)")
        else:
            # 旧版QQ使用后台模式
            logger.info(f"后台激活{hwnd} (旧版QQ)")
        time.sleep(sleep_time)
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
        logger.debug(f"设置剪贴板为{text}")
        
        if is_ntqq:
            # QQNT模式：前台粘贴
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x56, 0, 0, 0)  # V
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            logger.debug("前台粘贴V")
        else:
            # 旧版QQ模式：后台发送消息
            win32gui.SendMessage(hwnd, win32con.WM_PASTE, 0, 0)
            logger.debug("后台发送WM_PASTE")
        logger.info(f"粘贴{text}到{hwnd}")
        time.sleep(sleep_time)
        return True
    except Exception as e:
        logger.error(f"文本粘贴失败: {e}")
        return False

def paste_image_to_window(hwnd, image_data, is_ntqq):
    """粘贴图片到窗口，根据模式选择前台或后台粘贴"""
    try:
        image = Image.open(image_data)
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
            logger.debug("前台粘贴V")
        else:
            # 旧版QQ模式：后台发送消息
            win32gui.SendMessage(hwnd, win32con.WM_PASTE, 0, 0)
            logger.debug("后台发送WM_PASTE")
        logger.info(f"粘贴图片到{hwnd}")
        time.sleep(sleep_time)
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
            logger.debug("前台发送回车")
        else:
            # 旧版QQ模式：后台发送回车
            win32gui.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            win32gui.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
            logger.debug("后台发送回车")
        
        time.sleep(sleep_time)
        logger.info(f"发送回车到{hwnd}")
        return True
    except Exception as e:
        logger.error(f"发送回车失败: {e}")
        return False

try:
    for hwnd, title, cls in matched_windows:
        # 判断是否为QQNT模式
        if cls == "Chrome_WidgetWin_1":
            is_ntqq = True
            logger.info(f"检测到{hwnd}窗口{title}为{cls}，使用QQNT模式发送")
        else:
            is_ntqq = False
            logger.info(f"检测到{hwnd}窗口{title}为{cls}，使用旧版QQ模式发送")
        
        if not activate_window(hwnd, cls, is_ntqq):
            logger.error("窗口激活失败，跳过此窗口")
            continue

        if args.dry_run:
            logger.info("Dry-run模式：跳过实际发送")
            continue

        # @全体成员
        if final_at_all:
            paste_text_to_window(hwnd, "@", is_ntqq)
            send_enter_to_window(hwnd, is_ntqq)

        # 发送文本
        paste_text_to_window(hwnd, text, is_ntqq)

        # 发送图片
        if image_data:
            paste_image_to_window(hwnd, image_data, is_ntqq)

        # 最终发送
        send_enter_to_window(hwnd, is_ntqq)
        logger.info(f"消息已发送到窗口: {title}")
        
        # 窗口间延迟
        time.sleep(sleep_time)
        logger.debug(f"窗口间延迟{sleep_time}秒")
except Exception as e:
    logger.error(f"发送过程中出现错误: {e}")
exit(0)