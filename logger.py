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
        at_time = dtime(4, 0, 0)  # 凌晨4点
        super().__init__(
            filename=filename,
            when='midnight',
            interval=1,
            backupCount=backupCount,
            encoding='utf-8',
            atTime=at_time 
        )

    def getFilesToDelete(self):
        """获取需要删除的过期日志文件"""
        dir_name, base_name = os.path.split(self.baseFilename)
        file_names = os.listdir(dir_name)
        
        result = []
        prefix = base_name.replace('.log', '') + '_'
        for file_name in file_names:
            if file_name.startswith(prefix) and file_name.endswith('.log'):
                date_str = file_name[len(prefix):-4]
                try:
                    file_date = datetime.strptime(date_str, '%Y_%m_%d')
                    result.append((file_date, os.path.join(dir_name, file_name)))
                except ValueError:
                    pass
        
        result.sort(key=lambda x: x[0])
        if len(result) <= self.backup_count:
            return []
        
        return [f[1] for f in result[:len(result)-self.backup_count]]

def setup_logger(filename):
    """配置日志系统"""
    # 设置日志文件名格式
    date_str = datetime.now().strftime('%Y_%m_%d')
    log_file = os.path.join(log_dir, f'{filename}_{date_str}.log')
    
    file_handler = DailyRotatingFileHandler(log_file, backupCount=10)
    file_handler.setLevel(logging.DEBUG)  # 文件记录DEBUG及以上级别日志
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 控制台只输出INFO及以上级别日志
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception
    
    return logger
