import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, time as dtime

# 确保日志目录存在
log_dir = os.path.join(os.getcwd(), 'log')
os.makedirs(log_dir, exist_ok=True)

class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """自定义日志处理器，每天凌晨4点切分日志"""
    def __init__(self, filename, backupCount=10):
        self.backup_count = backupCount
        # 使用datetime.time对象替代time.struct_time
        at_time = dtime(4, 0, 0)  # 凌晨4点
        super().__init__(
            filename=filename,
            when='midnight',
            interval=1,
            backupCount=backupCount,
            encoding='utf-8',
            atTime=at_time  # 使用正确的datetime.time类型
        )

    def getFilesToDelete(self):
        """获取需要删除的过期日志文件"""
        # 获取所有日志文件
        dir_name, base_name = os.path.split(self.baseFilename)
        file_names = os.listdir(dir_name)
        
        # 筛选符合条件的日志文件
        result = []
        prefix = base_name.replace('.log', '') + '_'
        for file_name in file_names:
            if file_name.startswith(prefix) and file_name.endswith('.log'):
                date_str = file_name[len(prefix):-4]
                try:
                    # 解析文件名中的日期
                    file_date = datetime.strptime(date_str, '%Y_%m_%d')
                    result.append((file_date, os.path.join(dir_name, file_name)))
                except ValueError:
                    pass
        
        # 按日期排序并筛选需要删除的文件
        result.sort(key=lambda x: x[0])
        if len(result) <= self.backup_count:
            return []
        
        return [f[1] for f in result[:len(result)-self.backup_count]]

def setup_logger():
    """配置日志系统"""
    # 设置日志文件名格式
    date_str = datetime.now().strftime('%Y_%m_%d')
    log_file = os.path.join(log_dir, f'bot_{date_str}.log')
    
    # 创建自定义处理器
    file_handler = DailyRotatingFileHandler(log_file, backupCount=10)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    
    # 设置统一的日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 配置日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 添加错误处理
    def handle_exception(exc_type, exc_value, exc_traceback):
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception
    
    return logger

# 初始化日志系统
if __name__ == '__main__':
    logger = setup_logger()
    
    # 安全获取baseFilename
    file_handler = None
    for handler in logger.handlers:
        if isinstance(handler, DailyRotatingFileHandler):
            file_handler = handler
            break
    
    if file_handler:
        # 使用类型提示确保类型检查器知道这是TimedRotatingFileHandler
        timed_handler: TimedRotatingFileHandler = file_handler
        print(f"当前日志文件: {timed_handler.baseFilename}")
    else:
        print("未找到文件处理器")
    
    print("请等待至凌晨4点观察日志自动切分和清理")