"""
多账号系统。

每个账号代表一个独立的游戏账号，拥有自己的设置和宝藏基质配置。
"""

from __future__ import annotations

from typing import ClassVar, Final, Literal

from pydantic import BaseModel, Field

#: 各词条的最大等级（与游戏数值绑定，前端展示与后端校验共用同一来源）。
AFFIX1_MAX_LEVEL: Final[int] = 6
AFFIX2_MAX_LEVEL: Final[int] = 6
AFFIX3_MAX_LEVEL: Final[int] = 3

#: 默认账号的初始名称。默认账号可被重命名，改名后该字面量成为保留名，
#: 不允许其它账号占用（否则会与回退逻辑产生歧义）。
DEFAULT_PROFILE_NAME: Final[str] = "default"

#: 自定义基质在 treasure_matrix 中的 weapon_id 前缀，其后拼接稳定 ID。
CUSTOM_ID_PREFIX: Final[str] = "custom:"

#: 旧格式前缀（`custom_stat_{下标}`）。仅用于启动时的一次性迁移与识别，
#: 新写入一律使用 CUSTOM_ID_PREFIX。
LEGACY_CUSTOM_ID_PREFIX: Final[str] = "custom_stat_"


class TreasureMatrixEntry(BaseModel):
    """单个武器的宝藏基质配置及词条等级。"""

    weapon_id: str
    """武器 ID（例如 wpn_funnel_0009）。"""

    weapon_name: str = ""
    """武器显示名称（缓存以便使用）。"""

    affix1_level: int = Field(default=1, ge=1, le=AFFIX1_MAX_LEVEL)
    """第一词条（属性）等级：1-6。"""

    affix2_level: int = Field(default=1, ge=1, le=AFFIX2_MAX_LEVEL)
    """第二词条（副属性）等级：1-6。"""

    affix3_level: int = Field(default=1, ge=1, le=AFFIX3_MAX_LEVEL)
    """第三词条（技能）等级：1-3。"""

    include_in_calculation: bool = True
    """是否参与刷取建议计算，满级（6/6/3）默认为False。"""

    priority: int = Field(default=0, ge=0)
    """武器优先级，数值越大优先级越高。默认值0表示使用稀有度作为默认优先级。"""


class ProfileData(BaseModel):
    """单个账号存储的数据。"""

    _VERSION: ClassVar[int] = 1

    version: int = _VERSION

    name: str = "default"
    """账号显示名称。"""

    treasure_matrix: list[TreasureMatrixEntry] = Field(default_factory=list)
    """此账号保存的宝藏基质配置。"""

    weapon_overview_filters: dict[str, bool] = Field(
        default_factory=lambda: {
            "3star": True,
            "4star": True,
            "5star": True,
            "6star": True,
            "custom": True,
        }
    )
    """武器总览的星级过滤器配置。"""

    weapon_priorities: dict[str, int] = Field(default_factory=dict)
    """武器优先级配置，允许未拥有宝藏基质的武器也设置优先级。"""

    switch_display_mode: Literal["chip", "dot", "off"] = "chip"
    """武器总览"可切换"提示的显示模式：'chip'=标签, 'dot'=小圆点, 'off'=关闭。"""

    matrix_badge_display_mode: Literal["small", "medium", "off"] = "small"
    """武器总览基质图标显示模式：'small'=小号(默认), 'medium'=中号(2倍), 'off'=关闭。"""

    matrix_planner_farming_locations: dict[str, bool] = Field(default_factory=dict)
    """基质规划页刷取地点筛选配置。键为淤积点 battleId，值为是否勾选；
    缺失的键默认视为勾选（即默认全部勾选）。"""


class ProfileCollection(BaseModel):
    """所有账号的集合。"""

    _VERSION: ClassVar[int] = 1

    version: int = _VERSION

    active_profile: str = DEFAULT_PROFILE_NAME
    """当前激活的账号名称。"""

    default_profile: str = DEFAULT_PROFILE_NAME
    """默认账号的当前名称。

    默认账号可被重命名，重命名后该字段同步更新，用于删除保护与激活账号删除后的回退目标。
    """

    profiles: dict[str, ProfileData] = Field(default_factory=dict)
    """账号名称 -> 账号数据的映射。"""

    def get_active(self) -> ProfileData:
        """获取激活的账号数据，如果需要则创建默认账号。"""
        if self.active_profile not in self.profiles:
            self.profiles[self.active_profile] = ProfileData(name=self.active_profile)
        return self.profiles[self.active_profile]

    def ensure_default(self) -> None:
        """确保默认账号存在。"""
        if self.default_profile not in self.profiles:
            self.profiles[self.default_profile] = ProfileData(name=self.default_profile)
