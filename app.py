import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
import time
import subprocess
import signal
import platform

# 日志目录配置
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

class ControllerLogHandler(TimedRotatingFileHandler):
    def __init__(self):
        filename = os.path.join(LOG_DIR, "app.log")
        super().__init__(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        self.suffix = "%Y-%m-%d"
        self.namer = self._custom_namer

    @staticmethod
    def _custom_namer(default_name):
        base, ext = os.path.splitext(default_name)
        if "_" not in base:
            date_part = base.split(".")[-1]
            return f"{base.replace('.log','')}_{date_part}{ext}"
        return default_name

def setup_controller_logger():
    logger = logging.getLogger("Controller")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    file_handler = ControllerLogHandler()
    console_handler = logging.StreamHandler()

    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | [PID:%(process)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_controller_logger()

# 全局进程列表
child_processes = []

def signal_handler(sig, frame):
    logger.info("收到终止信号，清理子进程...")
    cleanup_processes()
    sys.exit(0)

def cleanup_processes():
    global child_processes
    for proc in child_processes:
        try:
            if proc.poll() is None:
                logger.info(f"终止进程 {proc.pid}")
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception as e:
            logger.error(f"终止进程失败: {str(e)}")
    child_processes.clear()

PROCESS_CONFIGS = [
    {
        'name': 'bot_dy',
        'command': ['python', 'bot.py', 'bot']
    },
    {
        'name': 'bot_live',
        'command': ['python', 'live.py', 'live']
    }
]

def launch_process(config):
    try:
        creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            config['command'],
            creationflags=creation_flags
        )
        child_processes.append(process)
        logger.info(f"启动进程 {config['name']} (PID:{process.pid})")
        return process
    except Exception as e:
        logger.error(f"启动失败 {config['name']}: {str(e)}")
        return None

def manage_processes():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    processes = {}
    
    for cfg in PROCESS_CONFIGS:
        proc = launch_process(cfg)
        if proc:
            processes[cfg['name']] = {
                'process': proc,
                'start_time': time.time(),
                'config': cfg
            }
    
    try:
        while True:
            time.sleep(60)
            
            for name, info in list(processes.items()):
                proc = info['process']
                cfg = info['config']
                
                status = proc.poll()
                
                if status is not None:
                    logger.warning(f"进程 {name} (PID:{proc.pid}) 异常退出，状态码: {status}")
                    new_proc = launch_process(cfg)
                    if new_proc:
                        processes[name] = {
                            'process': new_proc,
                            'start_time': time.time(),
                            'config': cfg
                        }
                elif time.time() - info['start_time'] > 600:
                    logger.info(f"定时重启 {name} (PID:{proc.pid})")
                    proc.terminate()
                    proc.wait()
                    new_proc = launch_process(cfg)
                    if new_proc:
                        processes[name] = {
                            'process': new_proc,
                            'start_time': time.time(),
                            'config': cfg
                        }
    finally:
        cleanup_processes()

if __name__ == "__main__":
    try:
        logger.info("====== 控制器启动 ======")
        manage_processes()
    except Exception as e:
        logger.error(f"未捕获异常: {str(e)}")
    finally:
        logger.info("====== 控制器关闭 ======")