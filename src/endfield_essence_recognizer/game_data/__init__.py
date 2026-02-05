from __future__ import annotations

import importlib.resources
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.abc import Traversable
    from typing import Any

    from endfield_essence_recognizer.game_data.models import (
        GemTable,
        GemTagIdTable,
        I18nTextTable,
        ItemTable,
        RarityColorTable,
        SkillPatchTable,
        TranslationKey,
        WeaponBasicTable,
        WikiEntryDataTable,
        WikiEntryTable,
        WikiGroupTable,
    )


def get_i18n_text_table_filename(language: str) -> str:
    """获取指定语言的翻译表文件名"""
    return f"I18nTextTable_{language}.json"


def load_json_file(path: Traversable) -> Any:
    """加载 JSON 文件并返回数据"""
    return json.loads(path.read_text(encoding="utf-8"))


def load_table_cfg(filename: str) -> Any:
    """
    加载 TableCfg 目录下的 JSON 文件并返回数据
    如果在 GitHub Actions 环境中运行，则返回空的递归默认字典（CI 中暂时无法使用实际数据）
    """
    import os

    if not os.environ.get("GITHUB_ACTIONS") == "true":
        return load_json_file(table_cfg_dir / filename)
    else:
        from collections import defaultdict

        def recursive_defaultdict():
            return defaultdict(recursive_defaultdict)

        return recursive_defaultdict()


def get_translation(text_data: TranslationKey, language: str) -> str:
    """
    获取翻译文本

    如果找不到翻译或翻译为空，返回原始文本
    """
    text_id = str(text_data["id"])
    text_content = text_data["text"]

    # 查找翻译表中的文本
    if language in i18n_text_tables and text_id in i18n_text_tables[language]:
        return i18n_text_tables[language][text_id]

    # 如果找不到翻译或翻译为空，使用原始文本
    return text_content


# 配置
CBT3_dir = importlib.resources.files("endfield_essence_recognizer") / "data"
table_cfg_dir = CBT3_dir / "endfielddata/TableCfg"
i18n_languages = ["CN", "EN", "JP", "KR", "MX", "RU", "TC"]
used_i18n_languages = ["CN"]

gem_table: GemTable = load_table_cfg("GemTable.json")
gem_tag_id_table: GemTagIdTable = load_table_cfg("GemTagIdTable.json")
item_table: ItemTable = load_table_cfg("ItemTable.json")
rarity_color_table: RarityColorTable = load_table_cfg("RarityColorTable.json")
skill_patch_table: SkillPatchTable = load_table_cfg("SkillPatchTable.json")
weapon_basic_table: WeaponBasicTable = load_table_cfg("WeaponBasicTable.json")
wiki_entry_data_table: WikiEntryDataTable = load_table_cfg("WikiEntryDataTable.json")
wiki_entry_table: WikiEntryTable = load_table_cfg("WikiEntryTable.json")
wiki_group_table: WikiGroupTable = load_table_cfg("WikiGroupTable.json")
# 读取所有语言的翻译表
i18n_text_tables: dict[str, I18nTextTable] = {}
for language in used_i18n_languages:
    i18n_text_tables[language] = load_table_cfg(get_i18n_text_table_filename(language))
