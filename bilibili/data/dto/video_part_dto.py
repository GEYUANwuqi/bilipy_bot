from typing import ClassVar

from base_cls import BaseDataModel


class VideoPartDto(BaseDataModel):
    """视频分段数据DTO"""
    discriminator_value: ClassVar[str] = "video_part"  # 数据类型标识

    start_timestamp: int  # 开始时间戳
    end_timestamp: int  # 结束时间戳
    content: str  # 字幕内容

    @classmethod
    def from_list(cls, data: list) -> list["VideoPartDto"]:
        """从列表构造DTO对象列表"""
        return [cls.model_validate(i) for i in data]
