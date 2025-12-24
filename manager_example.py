"""BiliManager使用示例"""
from manager import BiliManager
from event import DynamicData, LiveData
from typing import Literal
from utils import setup_logging
from logging import getLogger
import asyncio

setup_logging("DEBUG")
_log = getLogger("ManagerExample")

# 创建管理器实例
manager = BiliManager(sessdata="", poll_interval=12)

# 示例UID和房间ID
TEST_UID = 621240130  # 替换为实际的UID
TEST_ROOM_ID = 26498147  # 替换为实际的房间ID


async def send_qq(bat_text):
    """发送QQ消息"""
    _log.info(f"开始执行命令: {bat_text}")
    try:
        process = await asyncio.create_subprocess_shell(f'start /wait cmd /c {bat_text}', shell = True)
        return_code = await process.wait()
        if return_code == 0:
            _log.info("命令执行成功")
        else:
            _log.error(f"命令执行失败，返回码: {return_code}")
    except Exception as e:
        _log.error(f"命令执行异常: {e}")

# 1. 获取当前动态时回调
@manager.on_dynamic(uid=TEST_UID)
async def handle_get_dynamic(data: DynamicData):
    """每次轮询获取动态时都会触发_log.info"""
    _log.info(f"[获取动态] UP主: {data.up_info.name}, 动态类型: {data.base_info.type}")
    _log.info(f"  时间: {data.base_info.time}, ID: {data.base_info.id}")


@manager.on_dynamic(uid=1802011210)
async def handle_get_dynamic(data: DynamicData):
    """每次轮询获取动态时都会触发_log.info"""
    _log.info(f"[获取动态] UP主: {data.up_info.name}, 动态类型: {data.base_info.type}")
    _log.info(f"  时间: {data.base_info.time}, ID: {data.base_info.id}")

# 3. 有新动态时回调
@manager.on_new_dynamic(uid=TEST_UID)
async def handle_new_dynamic(data: DynamicData):
    """仅当检测到新动态时触发"""
    _log.info(f"[新动态] UP主 {data.up_info.name} 发布了新动态！")
    _log.info(f"  类型: {data.base_info.type}")
    _log.info(f"  链接: {data.base_info.jump_url}")

    # 根据动态类型处理
    if data.video_info:
        _log.info(f"  视频: {data.video_info.title}")
    elif data.base_info.text:
        _log.info(f"  内容: {data.base_info.text[:50]}...")


# 4. 获取直播状态回调（所有状态）
@manager.on_live(room_id=TEST_ROOM_ID)
async def handle_live_status(data: LiveData, status: Literal["open", "close", "opening", "default"]):
    """所有直播状态变化时都会触发"""
    _log.info(f"[直播状态] 当前状态: {status}")
    if status == "open":
        print(f"  {data.anchor_info.name} 开播了！")
        print(f"  标题: {data.room_info.title}")
    elif status == "close":
        print(f"  {data.anchor_info.name} 下播了")

# 4. 获取直播状态回调（所有状态）
@manager.on_live(room_id=22758221)
async def handle_live_status(data: LiveData, status: Literal["open", "close", "opening", "default"]):
    """所有直播状态变化时都会触发"""
    _log.info(f"[直播状态] 当前状态: {status}")
    if status == "open":
        print(f"  {data.anchor_info.name} 开播了！")
        print(f"  标题: {data.room_info.title}")
    elif status == "close":
        print(f"  {data.anchor_info.name} 下播了")

## 4.2 仅在下播时回调 - 发送QQ消息
#@manager.on_live_status(room_id=TEST_ROOM_ID, status="close")
#def handle_live_close(data: LiveData):
#    """仅在下播时触发，发送QQ消息"""
#    name = data.anchor_info.name
#    title = data.room_info.title
#    room_id = data.room_info.room_id
#    pic_url = data.room_info.cover_url
#
#    # 参考app.py的下播消息格式
#    live_msg = f"【下播通知】\n{name}下播啦！\n{title}\n直播地址：https://live.bilibili.com/{room_id}"
#
#    _log.info(f"[下播通知] {name} 下播了")
#
#    # 参考app.py发送QQ消息（下播不@全体成员）
#    encoded_text = base64.b64encode(live_msg.encode('utf-8')).decode('ascii')
#    bat_text = f'python send_qq.py -t "{encoded_text}" -p {pic_url} -a 0'
#
#    asyncio.create_task(send_qq(bat_text))

async def main():
    _log.info("启动BiliManager监控...")
    _log.info(f"监控UID: {manager._monitored_uids}")
    _log.info(f"监控房间: {manager._monitored_room_ids}")
    _log.info(f"当前轮询间隔: {manager.poll_interval} 秒")

    # 可以动态调整轮询间隔
    # manager.set_poll_interval(15)  # 修改为15秒

    # 启动监控

    try:
        # 主线程保持运行
        await manager.start()
        _log.info("监控已启动，按Ctrl+C停止...")
        await asyncio.sleep(30000)
        await manager.stop()
        #while True:
        #    await asyncio.sleep(1000000)

    except KeyboardInterrupt:
        _log.info("\n正在停止监控...")
        await manager.stop()
        _log.info("监控已停止")


if __name__ == "__main__":
    asyncio.run(main())


