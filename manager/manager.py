from event import LiveData, DynamicData
from api import BilibiliApi
from logging import getLogger

logger = getLogger(__name__)


class BiliManager:
    """BiliManager类，管理Bilibili相关功能."""

    def __init__(self, sessdata:str = ""):
        self.api = BilibiliApi(sessdata = sessdata)

