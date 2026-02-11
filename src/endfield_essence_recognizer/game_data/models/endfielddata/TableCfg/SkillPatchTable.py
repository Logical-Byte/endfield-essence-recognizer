from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class BlackboardEntry(TypedDict):
    """
    游戏引擎中技能参数的黑板报条目，无用
    """

    key: str
    """参数键名"""
    value: float
    """参数数字值"""
    valueStr: str
    """参数字符串值"""


class SkillPatchTableItem(TypedDict):
    blackboard: list[BlackboardEntry]
    """技能黑板报 (存储参数变量)，无用"""
    coolDown: float
    """技能冷却时间，无用"""
    costType: int
    """消耗资源类型，无用"""
    costValue: int
    """消耗资源数量，无用"""
    description: TranslationKey
    """技能详细描述 (指向翻译表的键)"""
    iconBgType: int
    """图标背景分类，无用"""
    iconId: str
    """技能图标 ID，无用"""
    level: int
    """技能等级。原表格把不同等级的技能放在同一个列表中，因此需要区分等级"""
    maxChargeTime: float
    """最大充能时间"""
    skillId: str
    """技能唯一ID"""
    skillName: TranslationKey
    """技能名称 (指向翻译表的键)"""
    subDescList: list[str]
    """附加说明列表"""
    subDescNameList: list[TranslationKey]
    """附加说明名称列表 (指向翻译表的键)"""
    tagId: str
    """
    技能对应的tag。

    我们需要通过这个tag来确定与这个技能完美匹配的基质是什么。
    具体来说，tagId和gemTagId是一一对应的关系，而gemTagId可以通过GemTagIdTable映射到gemTermId，从而找到对应的基质。
    """


class SkillPatchDataBundle(TypedDict):
    SkillPatchDataBundle: list[SkillPatchTableItem]
    """
    不同等级的同一个技能的集合。
    """


type SkillPatchTable = dict[str, SkillPatchDataBundle]
"""
skillId 映射到不同等级的技能数据集合。
"""
