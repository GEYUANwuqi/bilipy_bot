# BiliManager 使用文档
*注：文档由ai生成*

## 概述

`BiliManager` 是一个基于回调和装饰器的 Bilibili 监控管理器，支持动态和直播间的实时监控。

## 核心特性

1. **装饰器模式**: 使用装饰器简化回调注册
2. **多回调支持**: 同一事件可注册多个处理函数
3. **异步轮询**: 使用异步IO提高效率
4. **线程隔离**: 监控在独立线程中运行，不阻塞主线程
5. **数据管理**: 自动管理新旧数据，便于状态对比

## 快速开始

### 1. 初始化管理器

```python
from manager import BiliManager

# 创建管理器实例
manager = BiliManager(
    sessdata="your_sessdata_here",  # B站登录凭证
    poll_interval=10  # 轮询间隔（秒）
)
```

### 2. 注册回调函数

#### 装饰器1: `@on_get_dynamic` - 获取当前动态时回调

每次轮询都会触发，无论动态是否更新。

```python
@manager.on_get_dynamic(uid=123456)
def handle_dynamic(data: DynamicData):
    """处理函数必须接受一个DynamicData参数"""
    print(f"UP主: {data.up_info.name}")
    print(f"动态类型: {data.base_info.type}")
    print(f"发布时间: {data.base_info.time}")
```

#### 装饰器2: `@on_get_live` - 获取当前直播时回调

每次轮询都会触发，无论直播状态是否变化。

```python
@manager.on_get_live(room_id=12345)
def handle_live(data: LiveData):
    """处理函数必须接受一个LiveData参数"""
    print(f"主播: {data.anchor_info.name}")
    print(f"标题: {data.room_info.title}")
    print(f"状态: {data.room_info.live_status}")
    print(f"在线人数: {data.room_info.online}")
```

#### 装饰器3: `@on_new_dynamic` - 有新动态时回调

仅在检测到新动态时触发（通过时间戳判断）。

```python
@manager.on_new_dynamic(uid=123456)
def handle_new_dynamic(data: DynamicData):
    """处理函数必须接受一个DynamicData参数"""
    print(f"🆕 {data.up_info.name} 发布了新动态！")
    print(f"链接: {data.base_info.jump_url}")
    
    # 根据动态类型进行不同处理
    if data.video_info:
        print(f"视频标题: {data.video_info.title}")
    elif data.base_info.text:
        print(f"动态内容: {data.base_info.text}")
```

#### 装饰器4: `@on_live_status` - 获取直播状态回调

监控直播状态变化（开播/下播/直播中/未开播）。

```python
@manager.on_live_status(room_id=12345)
def handle_live_status(data: LiveData, status: Literal["open", "close", "opening", "default"]):
    """
    处理函数必须接受两个参数：
    - data: LiveData对象
    - status: 直播状态 ("open"开播, "close"下播, "opening"直播中, "default"未开播)
    """
    if status == "open":
        print(f"📺 {data.anchor_info.name} 开播了！")
        print(f"标题: {data.room_info.title}")
        print(f"链接: {data.room_info.jump_url}")
    elif status == "close":
        print(f"📴 {data.anchor_info.name} 下播了")
    elif status == "opening":
        print(f"🔴 {data.anchor_info.name} 正在直播，在线 {data.room_info.online} 人")
```

### 3. 启动和停止监控

```python
# 启动监控（在新线程中运行）
manager.start()

# 主线程继续执行其他任务
import time
while True:
    time.sleep(1)
    # 你的其他代码...

# 停止监控
manager.stop()
```

### 4. 动态调整轮询间隔

```python
# 获取当前轮询间隔
current_interval = manager.get_poll_interval()
print(f"当前轮询间隔: {current_interval} 秒")

# 设置新的轮询间隔（可以在运行时动态调整）
manager.set_poll_interval(15)  # 修改为15秒

# 示例：根据时间段调整轮询频率
import datetime

while True:
    hour = datetime.datetime.now().hour
    
    # 深夜降低轮询频率
    if 0 <= hour < 6:
        manager.set_poll_interval(30)  # 30秒轮询一次
    else:
        manager.set_poll_interval(10)  # 10秒轮询一次
    
    time.sleep(3600)  # 每小时检查一次
```

## 完整示例

```python
from manager import BiliManager
from event import DynamicData, LiveData
from typing import Literal
import time

# 创建管理器
manager = BiliManager(sessdata="your_sessdata", poll_interval=10)

# 注册多个回调处理新动态
@manager.on_new_dynamic(uid=123456)
def send_notification(data: DynamicData):
    """发送通知"""
    print(f"发送通知: {data.up_info.name} 发布了新动态")
    # 调用你的通知系统，如QQ、微信等

@manager.on_new_dynamic(uid=123456)
def log_dynamic(data: DynamicData):
    """记录日志"""
    print(f"记录日志: {data.base_info.id} - {data.base_info.type}")
    # 写入数据库或日志文件

# 监控直播状态变化
@manager.on_live_status(room_id=12345)
def handle_live_change(data: LiveData, status: Literal["open", "close", "opening", "default"]):
    """处理直播状态变化"""
    if status == "open":
        # 开播了，发送通知
        msg = f"{data.anchor_info.name} 开播了！快来看 {data.room_info.jump_url}"
        print(msg)
        # send_qq_message(msg)
    elif status == "close":
        # 下播了
        print(f"{data.anchor_info.name} 下播了")

# 启动监控
manager.start()

try:
    print("监控已启动，按Ctrl+C停止...")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("正在停止...")
    manager.stop()
    print("已停止")
```

## 数据类型说明

### DynamicData

动态数据对象，包含以下主要属性：

- `base_info: DynamicBaseData` - 动态基础信息
  - `type: str` - 动态类型
  - `id: str` - 动态ID
  - `time: str` - 发布时间
  - `timestamp: int` - 时间戳
  - `jump_url: str` - 动态链接
  - `text: str` - 文字内容（可选）
  
- `up_info: UPData` - UP主信息
  - `uid: int` - UID
  - `name: str` - 昵称
  - `face_url: str` - 头像URL
  
- `video_info: VideoData` - 视频信息（可选）
- `music_info: MusicData` - 音乐信息（可选）
- `article_info: ArticleData` - 专栏信息（可选）
- `live_rcmd_info: LiveRcmdData` - 直播推荐（可选）
- `forward_info: ForwardData` - 转发信息（可选）

### LiveData

直播数据对象，包含以下主要属性：

- `room_info: RoomInfo` - 直播间信息
  - `room_id: int` - 房间号
  - `title: str` - 标题
  - `live_status: int` - 直播状态（0未开播/1直播中/2轮播）
  - `online: int` - 在线人数
  - `jump_url: str` - 直播间链接
  
- `anchor_info: AnchorInfo` - 主播信息
  - `name: str` - 昵称
  - `face_url: str` - 头像URL
  
- `watched_show: WatchedShow` - 观看榜信息
- `notice_board: NoticeBoard` - 公告栏信息

## 高级用法

### 监控多个用户

```python
manager = BiliManager(sessdata="xxx", poll_interval=10)

# 监控多个UP主
@manager.on_new_dynamic(uid=111)
def handle_user1(data: DynamicData):
    print(f"用户1更新: {data.up_info.name}")

@manager.on_new_dynamic(uid=222)
def handle_user2(data: DynamicData):
    print(f"用户2更新: {data.up_info.name}")

@manager.on_new_dynamic(uid=333)
def handle_user3(data: DynamicData):
    print(f"用户3更新: {data.up_info.name}")

manager.start()
```

### 结合现有系统

```python
# 结合send_qq.py发送消息
import base64
import subprocess

@manager.on_new_dynamic(uid=123456)
def send_qq_notification(data: DynamicData):
    """发送QQ通知"""
    msg = f"【新动态】{data.up_info.name} 发布了新动态\n{data.base_info.jump_url}"
    encoded_text = base64.b64encode(msg.encode('utf-8')).decode('ascii')
    
    # 如果有图片
    if data.base_info.pics_url:
        pic_url = data.base_info.pics_url[0]
        cmd = f'python send_qq.py -t {encoded_text} -p {pic_url} -a 1'
    else:
        cmd = f'python send_qq.py -t {encoded_text} -a 1'
    
    subprocess.run(cmd, shell=True)
```

## 注意事项

1. **sessdata获取**: 需要从B站Cookie中获取有效的sessdata
2. **轮询间隔**: 建议设置10秒以上，避免频繁请求
3. **动态调整**: 可以使用 `set_poll_interval()` 方法在运行时动态调整轮询间隔
4. **线程安全**: 回调函数在监控线程中执行，注意线程安全
5. **异常处理**: 回调函数中的异常会被捕获并记录，不会影响其他回调
6. **数据初始化**: 首次获取数据时不会触发新动态/状态变化回调

## 与app.py的区别

原有的`app.py`实现存在以下问题：
- 代码耦合度高，难以维护
- 缺少清晰的事件处理机制
- 数据处理逻辑混乱
- 难以扩展

`BiliManager`的优势：
- ✅ 清晰的装饰器模式
- ✅ 解耦的数据处理
- ✅ 易于扩展和维护
- ✅ 支持多个回调
- ✅ 独立的线程管理
- ✅ 完善的错误处理

## 常见问题 FAQ

### Q1: 回调没有被触发？

**可能原因：**
1. 没有调用 `manager.start()` 启动监控
2. UID 或 room_id 不正确
3. sessdata 失效或无效
4. 用户没有动态或直播间不存在
5. 网络问题导致API请求失败

**解决方法：**
```python
# 1. 确保启动了监控
manager.start()

# 2. 检查是否正确注册
print(f"监控的UID: {manager._monitored_uids}")
print(f"监控的房间: {manager._monitored_room_ids}")

# 3. 查看日志输出
import logging
logging.basicConfig(level=logging.DEBUG)

# 4. 检查当前轮询间隔
print(f"轮询间隔: {manager.get_poll_interval} 秒")
```

### Q2: 提示"动态列表为空"错误？

**原因：** 该用户没有发布过任何动态。

**解决方法：** 这是正常情况，会记录为 WARNING 级别，不影响其他监控。如需忽略此警告，可以在注册前先检查用户是否有动态。

### Q3: 如何获取 sessdata？

**步骤：**
1. 登录 bilibili.com
2. 按 F12 打开开发者工具
3. 切换到 Application/存储 标签
4. 左侧找到 Cookies → https://www.bilibili.com
5. 找到名为 `SESSDATA` 的项，复制其值

**注意：** sessdata 可能会过期，需要定期更新。

### Q4: 监控线程意外停止？

**检查：**
```python
# 检查线程状态
if manager.monitor_thread:
    print(f"线程存活: {manager.monitor_thread.is_alive()}")
    print(f"运行状态: {manager._running}")

# 查看错误日志
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**常见原因：**
- 网络连接中断
- API 限流或返回错误
- 回调函数中的未捕获异常（已自动处理）

### Q5: 回调函数签名错误？

**正确签名：**
```python
# on_get_dynamic / on_new_dynamic
def callback(data: DynamicData) -> None:
    pass

# on_get_live
def callback(data: LiveData) -> None:
    pass

# on_live_status (不指定status参数时)
def callback(data: LiveData, status: Literal["open", "close", "opening", "default"]) -> None:
    pass

# on_live_status (指定status参数时)
def callback(data: LiveData) -> None:
    pass
```

### Q6: 如何调试回调函数？

**方法：**
```python
@manager.on_new_dynamic(uid=123456)
def debug_callback(data: DynamicData):
    """调试回调"""
    print("=" * 50)
    print(f"回调被触发！")
    print(f"UP主: {data.up_info.name}")
    print(f"类型: {data.base_info.type}")
    print(f"时间: {data.base_info.time}")
    print(f"完整数据: {data}")
    print("=" * 50)
    
    # 查看原始数据
    import json
    print(json.dumps(data.raw_data, indent=2, ensure_ascii=False))
```

### Q7: 如何处理高频轮询的性能问题？

**建议：**
```python
# 1. 合理设置轮询间隔（建议12秒以上）
manager = BiliManager(sessdata="xxx", poll_interval=12)

# 2. 根据直播状态动态调整
@manager.on_live_status(room_id=12345, status="open")
def on_open(data: LiveData):
    # 开播时提高频率
    manager.set_poll_interval(8)

@manager.on_live_status(room_id=12345, status="close")
def on_close(data: LiveData):
    # 下播后降低频率
    manager.set_poll_interval(15)

# 3. 避免在回调中执行耗时操作
# 使用线程池处理耗时任务
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=3)

@manager.on_new_dynamic(uid=123456)
def handle_async(data: DynamicData):
    # 异步处理，不阻塞轮询
    executor.submit(process_data, data)

def process_data(data):
    # 耗时操作
    pass
```

### Q8: 如何监控大量用户而不被限流？

**策略：**
```python
# 1. 增加轮询间隔
manager = BiliManager(sessdata="xxx", poll_interval=15)

# 2. 分批监控，错开时间
import time

users_batch1 = [111, 222, 333]
users_batch2 = [444, 555, 666]

manager1 = BiliManager(sessdata="xxx", poll_interval=20)
manager2 = BiliManager(sessdata="xxx", poll_interval=20)

for uid in users_batch1:
    # 注册到 manager1
    pass

for uid in users_batch2:
    # 注册到 manager2
    pass

manager1.start()
time.sleep(10)  # 错开启动时间
manager2.start()
```

### Q9: 状态过滤后回调还是被触发？

**检查：**
```python
# 确保状态参数正确
@manager.on_live_status(room_id=12345, status="open")  # 注意这里
def handle_open(data: LiveData):  # 不要接受 status 参数
    print("开播了")

# 而不是
@manager.on_live_status(room_id=12345, status="open")
def handle_open(data: LiveData, status):  # ❌ 错误：多余的参数
    print("开播了")
```

### Q10: 如何优雅地停止监控？

**推荐方式：**
```python
import signal
import sys

def signal_handler(sig, frame):
    """信号处理函数"""
    print('\n正在停止监控...')
    manager.stop()
    print('监控已停止')
    sys.exit(0)

# 注册信号处理
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

manager.start()
print('监控已启动，按 Ctrl+C 停止')

# 保持运行
signal.pause()  # Unix/Linux
# 或
# while True:
#     time.sleep(1)  # Windows
```

