from dataclasses import dataclass
from enum import StrEnum

type WeaponId = str
type StatId = str
type WeaponTypeId = int


class StatType(StrEnum):
    ATTRIBUTE = "ATTRIBUTE"
    """基质类型：主属性"""
    SECONDARY = "SECONDARY"
    """基质类型：次属性"""
    SKILL = "SKILL"
    """基质类型：技能"""


@dataclass(frozen=True, slots=True)
class WeaponV2:
    """表示游戏中的武器。"""

    weapon_id: WeaponId
    """主键、武器的唯一标识符（例如 wpn_funnel_0009）"""
    name: str
    """武器的中文显示名称"""
    weapon_type: WeaponTypeId
    """引用 WeaponType.json 中的武器类型 ID"""
    rarity: int
    """武器的稀有度级别（如 3, 4, 5）"""
    icon_id: str
    """武器的图标 ID，用于拼图标的 URL"""
    stat1_id: StatId | None
    """引用 EssenceStat 中的基质 ID（主属性槽位）"""
    stat2_id: StatId | None
    """引用 EssenceStat 中的基质 ID（次属性槽位）"""
    stat3_id: StatId | None
    """引用 EssenceStat 中的基质 ID（技能槽位）"""


@dataclass(frozen=True, slots=True)
class EssenceStatV2:
    """表示单个基质项或子状态/技能。"""

    stat_id: StatId
    """主键、基质的唯一标识符"""
    name: str
    """基质效果的中文显示名称"""
    type: StatType
    """基质类型：主属性、次属性或技能"""


@dataclass(frozen=True, slots=True)
class WeaponTypeV2:
    """将武器分类为不同的原型（例如剑、长柄武器）。"""

    weapon_type_id: WeaponTypeId
    """主键、武器类型的唯一标识符"""
    wiki_group_id: str
    """向下兼容的标识符（例如 wiki_group_weapon_sword），用于拼图标的 URL"""
    name: str
    """武器类型的中文显示名称"""
    icon_id: str
    """武器类型的图标 ID"""


@dataclass(frozen=True, slots=True)
class RarityColorV2:
    """将武器稀有度映射到其关联的颜色代码。"""

    rarity: int
    """武器稀有度级别（如 3, 4, 5）"""
    color: str
    """关联的十六进制颜色代码，以 '#' 开头"""
