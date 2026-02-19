from logging import getLogger
from typing import Optional, ClassVar
from base_cls import BaseDataModel

_log = getLogger("DanmakuMsgDTO")


class MedalInfoDto(BaseDataModel):
    """
    粉丝牌信息
    Tips:
        如果当前直播间或者用户开启了"优先展示当前直播间的粉丝勋章
        那么在该直播间无法获取到用户佩戴的其他主播的勋章信息"
    """
    level: int  # 勋章等级
    name: str  # 勋章名称
    anchor_name: str  # 主播名称
    room_id: int  # 主播房间号
    is_light: int  # 是否点亮 (1=点亮, 0=未点亮)
    anchor_uid: int  # 主播UID


class UserInfoDto(BaseDataModel):
    """
    用户基本信息
    """
    uid: int  # 用户UID
    username: str  # 用户名
    user_level: int  # 用户等级
    face: Optional[str] = None  # 头像URL


class DanmakuMsgDTO(BaseDataModel):
    """
    弹幕消息DTO
    """
    discriminator_value: ClassVar[str] = "danmaku_msg"  # 数据类型标识

    room_display_id: int  # 房间号
    room_real_id: int  # 房间真实ID
    message: str  # 弹幕内容
    user: UserInfoDto  # 用户信息
    medal: Optional[MedalInfoDto] = None  # 粉丝牌信息
    timestamp: int = 0  # 发送时间戳

    @classmethod
    def from_raw(cls, data: dict) -> "Optional[DanmakuMsgDTO]":
        """
        从原始API数据构造DTO对象
        注意: 由于弹幕数据格式特殊(数组形式), 需要先转换为字典格式
        """
        try:
            room_display_id = data.get("room_display_id", 0)
            room_real_id = data.get("room_real_id", 0)

            # 获取info数组
            info = data.get("data", {}).get("info", [])

            # 提取弹幕内容 info[1]
            message = info[1] if len(info) > 1 else ""

            # 提取用户基本信息 info[2]: [uid, username, admin, vip, svip, ...]
            user_basic = info[2] if len(info) > 2 else []
            uid = user_basic[0] if len(user_basic) > 0 else 0
            username = user_basic[1] if len(user_basic) > 1 else ""

            # 提取用户等级信息 info[4]: [level, ...]
            level_info = info[4] if len(info) > 4 else []
            user_level = level_info[0] if len(level_info) > 0 else 0

            # 提取头像 info[0][15].user.base
            face = None
            info_detail = info[0] if len(info) > 0 else []
            if isinstance(info_detail, list) and len(info_detail) > 15:
                user_detail_obj = info_detail[15]
                if isinstance(user_detail_obj, dict):
                    user_detail = user_detail_obj.get("user", {})
                    if user_detail:
                        base_info = user_detail.get("base", {})
                        face = base_info.get("face")

            # 提取粉丝牌信息 info[3]: [level, name, anchor_name, room_id, color, ...]
            medal_info = None
            medal_data = info[3] if len(info) > 3 else []
            if medal_data and len(medal_data) > 0:
                medal_info = {
                    "level": medal_data[0] if len(medal_data) > 0 else 0,
                    "name": medal_data[1] if len(medal_data) > 1 else "",
                    "anchor_name": medal_data[2] if len(medal_data) > 2 else "",
                    "room_id": medal_data[3] if len(medal_data) > 3 else 0,
                    "is_light": medal_data[11] if len(medal_data) > 11 else 0,
                    "anchor_uid": medal_data[12] if len(medal_data) > 12 else 0
                }

            # 提取时间戳 info[9].ts
            timestamp = 0
            if len(info) > 9 and isinstance(info[9], dict):
                timestamp = info[9].get("ts", 0)

            # 构造标准化字典后使用model_validate
            normalized_data = {
                "room_display_id": room_display_id,
                "room_real_id": room_real_id,
                "message": message,
                "user": {
                    "uid": uid,
                    "username": username,
                    "user_level": user_level,
                    "face": face
                },
                "medal": medal_info,
                "timestamp": timestamp
            }

            return cls.model_validate(normalized_data)

        except Exception as e:
            _log.error(f"解析弹幕数据失败: {e}", exc_info=True)
            return None
