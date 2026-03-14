from enum import StrEnum

from pydantic import BaseModel

from endfield_essence_recognizer.game_data.models.v2 import WeaponId


class TaskType(StrEnum):
    """表示希望 ScannerService 执行的任务类型"""

    ESSENCE = "essence"
    """扫描基质"""
    DELIVERY_CLAIM = "delivery_claim"
    """自动抢单"""


class WeaponEssenceCounts(BaseModel):
    """武器基质数量统计"""

    counts: dict[WeaponId, int]
    """各武器 ID 对应的匹配基质数量"""
