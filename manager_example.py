"""BiliManager使用示例"""
from manager import BiliManager
from event import Event
from utils import LiveType, DynamicType
from utils import setup_logging
from logging import getLogger
import asyncio

setup_logging("DEBUG")
_log = getLogger("BILIBILI")

# 创建管理器实例
manager = BiliManager(sessdata="", poll_interval=12)

# 示例UID和房间ID
# TEST_UID = [621240130,1802011210,3546729368520811]  # 替换为实际的UID
TEST_UID = [621240130]
TEST_ROOM_ID = [26498147, 22758221]  # 替换为实际的房间ID


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


@manager.on_dynamic(uid=TEST_UID)
async def handle_get_dynamic(event: Event):
    """每次轮询获取动态时都会触发"""
    _log.info(f"{event.data.up_info.name}的动态状态: {event.status}")
    # _log.info(f"[获取动态] UP主: {event.data.up_info.name}, 动态类型: {event.data.base_info.type}")
    # _log.info(f"  时间: {event.data.base_info.time}, ID: {event.data.base_info.id}")


@manager.on_dynamic(uid=TEST_UID, status=DynamicType.NEW)
async def handle_new_dynamic(event: Event):
    """仅当检测到新动态时触发"""
    _log.info(f"[新动态] UP主 {event.data.up_info.name} 发布了新动态！")
    _log.info(event.data)


@manager.on_dynamic(uid=TEST_UID, status=DynamicType.DELETED)
async def handle_del_dynamic(event: Event):
    """仅当检测到删除动态时触发"""
    _log.info(f"[删除动态] UP主 {event.data.up_info.name} 删除了动态{event.data.base_info.text}！")


@manager.on_live(room_id=TEST_ROOM_ID)
async def handle_live_status(event: Event):
    """所有直播状态变化时都会触发"""
    _log.info(f"[直播状态] {event.data.anchor_info.name}当前状态: {event.status}")


@manager.on_live(room_id=TEST_ROOM_ID, status=LiveType.ONLINE)
async def handle_live_opening(event: Event):
    """直播中时触发"""
    _log.info(f"{event.data.anchor_info.name}在直播")


# 4.2 仅在下播时回调 - 发送QQ消息
# @manager.on_live_status(room_id=TEST_ROOM_ID, status="close")
# def handle_live_close(data: LiveData):
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
    _log.info(f"监控UID: {manager.uids}")
    _log.info(f"监控房间: {manager.room_ids}")
    _log.info(f"当前轮询间隔: {manager.poll_interval} 秒")

    # 可以动态调整轮询间隔
    # manager.set_poll_interval(15)  # 修改为15秒

    # 启动监控

    try:
        # 主线程保持运行
        manager.start()
        _log.info("监控已启动，按Ctrl+C停止...")
        await asyncio.sleep(300)
        manager.stop()
        # while True:
        #    await asyncio.sleep(1000000)

    except KeyboardInterrupt:
        _log.info("\n正在停止监控...")
        manager.stop()
        _log.info("监控已停止")


if __name__ == "__main__":
    asyncio.run(main())
