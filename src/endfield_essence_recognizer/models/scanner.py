from enum import StrEnum


class TaskType(StrEnum):
    """表示希望 ScannerService 执行的任务类型"""

    ESSENCE = "essence"
    """扫描基质"""
    DELIVERY_CLAIM = "delivery_claim"
    """自动抢单"""
