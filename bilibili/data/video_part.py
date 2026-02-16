from dataclasses import dataclass

from base_cls import BaseData
from .dto import (
    VideoPartDto,
)


@dataclass(frozen=True)
class VideoPartData(BaseData):
    """
    视频字幕数据
    """
    start_timestamp: int  # 开始时间戳
    end_timestamp: int  # 结束时间戳
    content: str  # 字幕内容

    @classmethod
    def from_dto_list(cls, dto_list: list[VideoPartDto]) -> list["VideoPartData"]:
        """从DTO对象列表构造VideoPartData实例列表

        Args:
            dto_list: VideoPartDto对象列表

        Returns:
            VideoPartData实例列表
        """
        return [cls.from_dto(dto) for dto in dto_list]

    @classmethod
    def from_dto(cls, dto: VideoPartDto) -> "VideoPartData":
        """从DTO对象构造VideoPartData实例

        Args:
            dto: VideoPartDto对象

        Returns:
            VideoPartData实例
        """
        return cls(
            start_timestamp = dto.start_timestamp,
            end_timestamp = dto.end_timestamp,
            content = dto.content,
        )
