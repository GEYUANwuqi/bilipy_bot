from pydantic import BaseModel, ConfigDict
from logging import getLogger


_log = getLogger("DynamicDTO")


class BaseDto(BaseModel):
    """
    DTO基类
    """
    model_config = ConfigDict(
        strict = False,
        frozen = True,
        extra = 'ignore',
    )
