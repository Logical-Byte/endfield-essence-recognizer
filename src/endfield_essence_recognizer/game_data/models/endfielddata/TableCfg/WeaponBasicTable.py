from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class WeaponBasic(TypedDict):
    breakthroughTemplateId: str
    """武器突破模板 ID，无用"""
    engName: TranslationKey
    """英文/本地化名称 标识"""
    levelTemplateId: str
    """升级属性成长模板 ID，无用"""
    maxLv: int
    """武器最大等级，无用"""
    modelPath: str
    """3D 模型资源路径，无用"""
    potentialUpItemList: list[str]
    """潜能提升所需物品 ID 列表 (对应 ItemTable)，无用"""
    rarity: int
    """稀有度等级，整数"""
    talentTemplateId: str
    """天赋模板 ID，无用"""
    weaponDesc: TranslationKey
    """武器描述 (指向翻译表的键)，无用"""
    weaponId: str
    """武器唯一 ID (对应 ItemTable 中的 ID)，例如：wpn_funnel_0009"""
    weaponPotentialSkill: str
    """一个skillId（SkillPatchTable的主键），表示武器的潜能能够提升的技能。"""
    weaponSkillList: list[str]
    """2到3个skillId (SkillPatchTable 的键)，表示武器的2到3个技能。"""
    weaponType: int
    """表示武器类型的整数，现在是1到6之间"""


type WeaponBasicTable = dict[str, WeaponBasic]
"""
根据主键 weaponId 映射到武器基础数据对象。
"""
