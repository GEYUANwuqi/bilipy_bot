# -------------------------
# @Author       : Fish-LP fish.zh@outlook.com
# @Date         : 2025-02-12 13:41:02
# @LastEditors  : Fish-LP fish.zh@outlook.com
# @LastEditTime : 2025-06-22 21:51:42
# @Description  : 日志格式化
# @Copyright (c) 2025 by Fish-LP, MIT 使用许可协议
# -------------------------
import logging
import os
import json
import warnings
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from .color import Color
try:
    from tqdm import tqdm as tqdm_original # type: ignore
except ImportError:
    tqdm_original = None

__author__  = "Fish-LP <Fish.zh@outlook.com>"
__status__  = "dev"
__version__ = "2.1.1-dev"

# NOTE: 这里保存的是针对不同目标（console/file）和不同日志级别的消息格式模板
LOG_MESSAGE_FORMATS = {
    "console": {
        "DEBUG": f"{Color.CYAN}[%(asctime)s.%(msecs)s]{Color.RESET} "
            f"{Color.BLUE}%(colored_levelname)-8s{Color.RESET} "
            f"{Color.GRAY}[%(threadName)s|%(processName)s]{Color.RESET} "
            f"{Color.MAGENTA}%(name)s{Color.RESET} "
            f"{Color.YELLOW}%(filename)s:%(lineno)d %(funcName)s{Color.RESET} "
            f"{Color.RESET}| %(message)s{Color.RESET}",
            
        "INFO": f"{Color.CYAN}[%(asctime)s]{Color.RESET} "
            f"{Color.GREEN}%(colored_levelname)-8s{Color.RESET} "
            f"{Color.MAGENTA}%(name)s{Color.RESET} ➜ "
            f"{Color.RESET}%(message)s{Color.RESET}",
            
        "WARNING": f"{Color.CYAN}[%(asctime)s]{Color.RESET} "
            f"{Color.YELLOW}%(colored_levelname)-8s{Color.RESET} "
            f"{Color.MAGENTA}%(name)s{Color.RESET} "
            f"{Color.YELLOW}➜{Color.RESET} "
            f"{Color.RESET}%(message)s{Color.RESET}",
            
        "ERROR": f"{Color.CYAN}[%(asctime)s]{Color.RESET} "
            f"{Color.RED}%(colored_levelname)-8s{Color.RESET} "
            f"{Color.GRAY}[%(filename)s]{Color.RESET}"
            f"{Color.MAGENTA}%(name)s:%(lineno)d{Color.RESET} "
            f"{Color.RED}➜{Color.RESET} "
            f"{Color.RESET}%(message)s{Color.RESET}",
            
        "CRITICAL": f"{Color.CYAN}[%(asctime)s]{Color.RESET} "
                f"{Color.RED}{Color.BOLD}%(colored_levelname)-8s{Color.RESET} "
                f"{Color.GRAY}{{%(module)s}}{Color.RESET}"
                f"{Color.MAGENTA}[%(filename)s]{Color.RESET}"
                f"{Color.MAGENTA}%(name)s:%(lineno)d{Color.RESET} "
                f"{Color.RED}➜{Color.RESET} "
                f"{Color.RESET}%(message)s{Color.RESET}"
    },
    "file": {
        "DEBUG": "[%(asctime)s] %(levelname)-8s [%(threadName)s|%(processName)s] %(name)s (%(filename)s:%(funcName)s:%(lineno)d) | %(message)s",
        "INFO": "[%(asctime)s] %(levelname)-8s %(name)s ➜ %(message)s",
        "WARNING": "[%(asctime)s] %(levelname)-8s %(name)s ➜ %(message)s",
        "ERROR": "[%(asctime)s] %(levelname)-8s [%(filename)s]%(name)s:%(lineno)d ➜ %(message)s",
        "CRITICAL": "[%(asctime)s] %(levelname)-8s {%(module)s}[%(filename)s]%(name)s:%(lineno)d ➜ %(message)s",
    }
}

if not tqdm_original is None:
    class tqdm(tqdm_original):
        """
        自定义 tqdm 类的初始化方法
        通过设置默认参数,确保每次创建 tqdm 进度条时都能应用统一的风格

        参数说明: 
        :param args: 原生 tqdm 支持的非关键字参数（如可迭代对象等）
        :param kwargs: 原生 tqdm 支持的关键字参数,用于自定义进度条的行为和外观
            - bar_format (str): 进度条的格式化字符串
            - ncols (int): 进度条的宽度（以字符为单位）
            - colour (str): 进度条的颜色
            - desc (str): 进度条的描述信息
            - unit (str): 进度条的单位
            - leave (bool): 进度条完成后是否保留显示
        """
        _STYLE_MAP = {
            "BLACK": Color.BLACK,
            "RED": Color.RED,
            "GREEN": Color.GREEN,
            "YELLOW": Color.YELLOW,
            "BLUE": Color.BLUE,
            "MAGENTA": Color.MAGENTA,
            "CYAN": Color.CYAN,
            "WHITE": Color.WHITE,
        }
        
        def __init__(self, *args, **kwargs):
            # 保存颜色参数以便后续处理
            self._custom_colour = kwargs.get("colour", "GREEN")
            
            # 设置默认进度条格式
            kwargs.setdefault("bar_format", 
                f"{Color.CYAN}{{desc}}{Color.RESET} "
                f"{Color.WHITE}{{percentage:3.0f}}%{Color.RESET} "
                f"{Color.GRAY}[{{n_fmt}}]{Color.RESET}"
                f"{Color.WHITE}|{{bar:20}}|{Color.RESET}"
                f"{Color.BLUE}[{{elapsed}}]{Color.RESET}"
            )
            kwargs.setdefault("ncols", 80)
            kwargs.setdefault("colour", None)  # 避免基类处理颜色
            
            super().__init__(*args, **kwargs)
            
            # 在初始化完成后应用颜色
            self.colour = self._custom_colour
            
        @property
        def colour(self):
            return self._colour
            
        @colour.setter 
        def colour(self, color):
            # 确保颜色值有效
            if not color:
                color = "GREEN"
                
            color_upper = color.upper()
            valid_color = self._STYLE_MAP.get(color_upper, "GREEN")
            
            # 保存颜色值
            self._colour = color_upper
            
            # 更新描述信息颜色
            if hasattr(self, 'GREEN') and self.desc:
                self.desc = f"{getattr(Color, valid_color)}{self.desc}{Color.RESET}"


# 日志级别颜色映射
LOG_LEVEL_TO_COLOR = {
    "DEBUG": Color.CYAN,
    "INFO": Color.GREEN,
    "WARNING": Color.YELLOW,
    "ERROR": Color.RED,
    "CRITICAL": Color.MAGENTA,
}


# 定义动态格式化器，根据日志级别选择不同的格式
class DynamicFormatter(logging.Formatter):
    """根据日志记录级别动态选择格式的格式化器"""
    
    def __init__(self, fmt_dict: dict, datefmt: str = None, use_color: bool = True):
        """
        初始化动态格式化器
        
        Args:
            fmt_dict: 包含不同日志级别格式字符串的字典，键为级别名称（如"DEBUG"）
            datefmt: 日期时间格式字符串
            use_color: 是否使用颜色
        """
        super().__init__(datefmt=datefmt)
        self.fmt_dict = fmt_dict
        self.use_color = use_color
        
        # 为每个级别预创建Formatter实例，提高性能
        self._formatters = {}
        for level_name, fmt in fmt_dict.items():
            self._formatters[level_name] = logging.Formatter(fmt, datefmt=datefmt)
        
        # 默认格式（使用第一个可用的格式）
        self._default_formatter = list(self._formatters.values())[0]
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，根据记录级别选择对应的格式"""
        # 动态颜色处理
        if self.use_color:
            record.colored_levelname = (
                f"{LOG_LEVEL_TO_COLOR.get(record.levelname, Color.RESET)}"
                f"{record.levelname:8}"
                f"{Color.RESET}"
            )
            # 添加统一颜色字段
            record.colored_name = f"{Color.MAGENTA}{record.name}{Color.RESET}"
            # 添加毫秒信息用于ERROR级别格式
        else:
            record.colored_levelname = record.levelname
            record.colored_name = record.name
        
        # 根据记录级别选择格式
        level_name = record.levelname
        formatter = self._formatters.get(level_name, self._default_formatter)
        
        try:
            return formatter.format(record)
        except Exception as e:
            warnings.warn(f"日志格式化错误: {str(e)}")
            # 使用默认格式作为备选
            return self._default_formatter.format(record)


def _get_valid_log_level(level_name: str, default: str):
    """验证并获取有效的日志级别"""
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        warnings.warn(f"Invalid log level: {level_name}, using {default} instead.")
        return getattr(logging, default)
    return level


def setup_logging(console_level = None):
    """设置日志系统，支持根据记录器名称重定向到不同文件"""
    # 环境变量读取
    console_level = console_level or os.getenv("LOG_LEVEL", "INFO").upper()
    file_level = os.getenv("FILE_LOG_LEVEL", "DEBUG").upper()
    
    # 验证并转换日志级别
    console_log_level = _get_valid_log_level(console_level, "INFO")
    file_log_level = _get_valid_log_level(file_level, "DEBUG")
    
    # 文件路径配置 - 使用固定名称，不使用日期
    log_dir = os.getenv("LOG_FILE_PATH", "./logs")
    file_name = os.getenv("LOG_FILE_NAME", "bot.log")  # 改为固定名称
    
    # 备份数量验证
    try:
        backup_count = int(os.getenv("BACKUP_COUNT", "7"))
    except ValueError:
        backup_count = 7
        warnings.warn("BACKUP_COUNT 为无效值,使用默认值 7")
        os.environ["BACKUP_COUNT"] = "7"

    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    root_file_path = os.path.join(log_dir, file_name)  # 直接使用固定名称

    # ===== 1. 配置根记录器 =====
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 控制台处理器 - 使用动态格式化器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_log_level)
    console_formatter = DynamicFormatter(
        fmt_dict=LOG_MESSAGE_FORMATS["console"],
        datefmt='%H:%M:%S',
        use_color=True
    )
    console_handler.setFormatter(console_formatter)
    
    # 根记录器的文件处理器 - 使用动态格式化器（无颜色）
    root_file_handler = TimedRotatingFileHandler(
        filename=root_file_path,
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
        utc=True  # 使用UTC时间避免时区问题
    )
    root_file_handler.setLevel(file_log_level)
    file_formatter = DynamicFormatter(
        fmt_dict=LOG_MESSAGE_FORMATS["file"],
        datefmt='%Y-%m-%d %H:%M:%S',
        use_color=False
    )
    root_file_handler.setFormatter(file_formatter)
    
    # 添加处理器到根记录器
    root_logger.handlers = [console_handler, root_file_handler]
    
    # ===== 2. 配置重定向记录器 =====
    # 从环境变量读取重定向配置
    redirect_rules_json = os.getenv("LOG_REDIRECT_RULES", "{}")
    try:
        redirect_rules = json.loads(redirect_rules_json)
    except json.JSONDecodeError:
        redirect_rules = {}
        warnings.warn("Invalid LOG_REDIRECT_RULES format. Using default rules.")
    
    # 为每个重定向规则创建记录器和处理器
    for logger_name, filename in redirect_rules.items():
        # 创建完整的文件路径
        redirect_file_path = os.path.join(log_dir, filename)
        
        # 创建文件处理器
        file_handler = TimedRotatingFileHandler(
            filename=redirect_file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            utc=True
        )
        file_handler.setLevel(file_log_level)
        # 为每个重定向记录器也使用动态格式化器
        file_handler.setFormatter(file_formatter)
        
        # 创建记录器并添加处理器
        logger = logging.getLogger(logger_name)
        logger.setLevel(file_log_level)
        logger.addHandler(file_handler)
        
        # 关键：禁止传播到根记录器，避免重复记录
        logger.propagate = False


# 初始化日志配置
setup_logging()

def get_log(name='Logger'):
    """
    获取日志记录器
    """
    warnings.warn("The 'get_log' method is deprecated, "
        "use 'logging.getLogger' instead", DeprecationWarning, 2)
    return logging.getLogger(name)


# 示例用法
if __name__ == "__main__":
    from time import sleep
    # 获取不同记录器的日志
    root_logger = logging.getLogger()
    db_logger = logging.getLogger("database")
    net_logger = logging.getLogger("network")
    sec_logger = logging.getLogger("security")
    setup_logging("DEBUG")
    
    print("测试不同级别的日志输出（使用动态格式）：")
    root_logger.debug("根记录器调试信息")
    root_logger.info("根记录器普通信息")
    root_logger.warning("根记录器警告信息")
    net_logger.error("网络错误: 连接超时")
    sec_logger.critical("安全警报: 检测到异常登录尝试")
    
    # 测试不同格式的差异
    print("\n测试不同日志级别的格式差异：")
    root_logger.debug("调试信息 - 包含文件名、行号和函数名")
    root_logger.info("普通信息 - 简洁格式")
    root_logger.warning("警告信息 - 带警告符号")
    root_logger.error("错误信息 - 包含文件名和行号")
    root_logger.critical("严重错误 - 包含模块名和文件名")