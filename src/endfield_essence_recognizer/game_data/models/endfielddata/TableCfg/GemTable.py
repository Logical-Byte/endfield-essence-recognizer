from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class Gem(TypedDict):
    """描述一个基质"""

    gemTermId: str
    """基质主键 (基质类型的唯一标识符) 例如：gat_passive_attr_agi"""
    isSkillTerm: bool
    """是否为技能相关的项"""
    sortOrder: int
    """显示排序优先级"""
    tagDesc: TranslationKey
    """Tag 本地化描述 (指向翻译表的键)，基本无用"""
    tagIcon: str
    """Tag 的图标，无用"""
    tagId: str
    """Tag ID: tag的主键。tag 表示基质的属性类型，例如：敏捷提升、追袭

    事实上，GemTagIdTable 中定义了 tagId 到 gemTabId 的函数确定关系，因此
    gemTagId 和 gemTermId 是一一对应的关系；但是武器技能表中关联的外键是tagId而非 gemTermId。
    """
    tagName: TranslationKey
    """Tag 本地化名称 (指向翻译表的键) 例: 敏捷提升、追袭"""
    termType: int
    """基质属性分类 (0: 基础属性, 1: 附加属性, 2: 技能属性)"""


type GemTable = dict[str, Gem]
"""
根据主键 gemTermId 映射到基质对象。
"""
