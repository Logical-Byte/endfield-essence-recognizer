from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from endfield_essence_recognizer.updater.mirrors import MIRRORS
from endfield_essence_recognizer.updater.sources import (
    DEFAULT_UPDATE_FLOW,
    LEGACY_FLOW_ALIASES,
    YITULIU_FLOW,
    normalize_update_flow,
)


class Action(StrEnum):
    KEEP = "keep"
    LOCK = "lock"
    DEPRECATE = "deprecate"
    UNLOCK = "unlock"
    UNDEPRECATE = "undeprecate"
    UNLOCK_AND_UNDEPRECATE = "unlock_and_undeprecate"
    DEPRECATE_IF_NOT_LOCKED = "deprecate_if_not_locked"
    LOCK_IF_NOT_DEPRECATED = "lock_if_not_deprecated"
    DEPRECATE_IF_MISSING_STATS = "deprecate_if_missing_stats"


class NonFiveStarBehavior(StrEnum):
    """Enumeration of behaviors for non-5-star essences.

    5-star 即高纯基质（黄色），非5-star即非高纯基质。
    """

    PROCESS = "process"
    """Process non-5-star essences normally according to other rules."""

    SKIP = "skip"
    """Skip any operations on non-5-star essences."""

    STOP = "stop"
    """Stop the current scan when a non-5-star essence is encountered."""

    HIGH_LEVEL_ONLY = "high_level_only"
    """仅对非无瑕基质进行高等级属性词条判定，不判定武器匹配。"""


class TreasureMatchMode(StrEnum):
    """How configured treasure conditions are matched."""

    ONLY = "only"
    """Only configured slots are checked; unconfigured slots are ignored."""

    ALL = "all"
    """All three slots must be configured and matched."""

    ANY = "any"
    """Any configured slot can match."""

    SUM = "sum"
    """三项词条等级之和达到设定阈值即匹配（仅用于高等级属性判定）。"""


class SameTypeGroupMode(StrEnum):
    """同类型宝藏基质的分组方式。"""

    BY_STAT = "by_stat"
    """按三个词条名称分组（属性组合相同即为同类型）。"""

    BY_WEAPON = "by_weapon"
    """按武器分组（每把武器独立计数，相同属性组合的不同武器互不影响）。"""


class KeepBestMode(StrEnum):
    """留大弃小策略中，等级比较的方式。"""

    SEQUENTIAL = "sequential"
    """依次比对：从左到右逐维度比较 A → B → C。"""

    SUM = "sum"
    """和值比对：比较三个词条等级之和 A + B + C。"""

    GREASE = "grease"
    """冷却脂消耗：按从 1 级升到该等级所需的冷却脂总量比较（1/1/1 视作 0）。"""

    WEIGHTED_SUM = "weighted_sum"
    """概率和值：按升级难度加权比较（等级越高越难升，权重越大）。"""


class CleanupTriggerMode(StrEnum):
    """冗余清理（实验性）的触发时机。"""

    SCAN_COMPLETE = "scan_complete"
    """仅在扫描到尾页（自然完成）时清理。"""

    ALWAYS = "always"
    """所有情况下均清理（含手动停止扫描）。"""


class EssenceStats(BaseModel):
    """自定义宝藏基质属性组合，支持可选的显示名称。"""

    id: str = ""
    """稳定标识符，创建时生成后不再变化。

    宝藏基质在 profile 中以 `custom:{id}` 的形式被引用。用列表下标做标识会
    让每次删除都必须重写所有下游引用，稍有遗漏就造成数据错位；空字符串表示
    尚未分配（旧配置），由 `UserSettingManager` 在加载时补齐。
    """
    name: str = ""
    """自定义显示名称，用于武器总览页面展示。"""
    attribute: str | None = None
    """基础属性 ID，None 表示不限制。"""
    secondary: str | None = None
    """附加属性 ID，None 表示不限制。"""
    skill: str | None = None
    """技能属性 ID，None 表示不限制。"""
    no_prompt_switch: bool = False
    """勾选"不再提示"后为 True，跳过对该自定义基质与内置武器的重合检查。"""


class UserSetting(BaseModel):
    _VERSION: ClassVar[int] = 9
    _same_type_treasure_counts: dict[tuple[str | None, ...], int] = PrivateAttr(
        default_factory=dict
    )
    _same_type_best_levels: dict[tuple[str | None, ...] | str, tuple[int, int, int]] = (
        PrivateAttr(default_factory=dict)
    )
    # 每个分组（stat_key 或 weapon_id）中，等级与已记录最佳等级相等时还可“跳过”
    # 的次数；由 profile 中已保存的同等级基质数量初始化，用于完整扫描时避免把
    # 已保存的那几枚误判为多出来的重复品。
    _same_type_equal_skips: dict[tuple[str | None, ...] | str, int] = PrivateAttr(
        default_factory=dict
    )

    version: int = _VERSION

    trash_weapon_ids: list[str] = []
    treasure_essence_stats: list[EssenceStats] = []
    treasure_essence_match_mode: TreasureMatchMode = TreasureMatchMode.ALL

    treasure_action: Action = Action.LOCK
    trash_action: Action = Action.UNLOCK

    non_five_star_behavior: NonFiveStarBehavior = NonFiveStarBehavior.PROCESS
    """如何处理非高纯基质：正常处理或直接跳过。"""

    high_level_treasure_enabled: bool = False
    """是否启用高等级基质属性词条判定为宝藏"""
    high_level_treasure_attribute_threshold: int = Field(default=3, ge=1, le=6)
    """高等级基础属性词条的等级阈值（+1~+6）"""
    high_level_treasure_secondary_threshold: int = Field(default=3, ge=1, le=6)
    """高等级附加属性词条的等级阈值（+1~+6）"""
    high_level_treasure_skill_threshold: int = Field(default=3, ge=1, le=3)
    """高等级技能属性词条的等级阈值（+1~+3）"""
    high_level_treasure_match_mode: TreasureMatchMode = TreasureMatchMode.ANY
    """高等级属性词条的匹配方式：仅/和/或/三项相加。"""
    high_level_treasure_sum_threshold: int = Field(default=6, ge=3, le=15)
    """三项相加模式下，三个词条等级之和的阈值（3~15）。"""
    high_level_treasure_only_check_attribute: bool = True
    """仅模式下是否检查基础属性槽位"""
    high_level_treasure_only_check_secondary: bool = True
    """仅模式下是否检查附加属性槽位"""
    high_level_treasure_only_check_skill: bool = True
    """仅模式下是否检查技能属性槽位"""

    # 非无瑕基质专用的高等级判定设置
    non_five_star_separate_high_level_settings: bool = False
    """是否为非无瑕基质启用独立的高等级属性词条判定设置"""
    non_five_star_high_level_attribute_threshold: int = Field(default=3, ge=1, le=6)
    """非无瑕基质高等级基础属性词条的等级阈值（+1~+6）"""
    non_five_star_high_level_secondary_threshold: int = Field(default=3, ge=1, le=6)
    """非无瑕基质高等级附加属性词条的等级阈值（+1~+6）"""
    non_five_star_high_level_skill_threshold: int = Field(default=3, ge=1, le=3)
    """非无瑕基质高等级技能属性词条的等级阈值（+1~+3）"""
    non_five_star_high_level_match_mode: TreasureMatchMode = TreasureMatchMode.ANY
    """非无瑕基质高等级属性词条的匹配方式：仅/和/或/三项相加。"""
    non_five_star_high_level_sum_threshold: int = Field(default=6, ge=3, le=15)
    """非无瑕基质三项相加模式下，三个词条等级之和的阈值（3~15）。"""
    non_five_star_high_level_only_check_attribute: bool = True
    """非无瑕基质仅模式下是否检查基础属性槽位"""
    non_five_star_high_level_only_check_secondary: bool = True
    """非无瑕基质仅模式下是否检查附加属性槽位"""
    non_five_star_high_level_only_check_skill: bool = True
    """非无瑕基质仅模式下是否检查技能属性槽位"""

    same_type_treasure_limit_enabled: bool = True
    """是否启用同类型宝藏基质数量上限。"""
    same_type_treasure_limit: int = Field(default=1, ge=1, le=999)
    """每类宝藏基质允许保留的数量上限；超过后视为养成材料。"""

    same_type_group_mode: SameTypeGroupMode = SameTypeGroupMode.BY_WEAPON
    """同类型宝藏基质的分组方式：按基质划分 / 按武器划分。"""

    same_type_keep_best: bool = True
    """启用留大弃小策略：同类型中保留等级更高的基质，等级更低的视为养成材料。"""

    same_type_non_downgrade_filter: bool = True
    """按武器划分时，过滤掉无法升级任何匹配武器已有基质的矩阵（非降级原则）。
    启用后，基质各维度等级必须 >= 武器当前等级才会被保留，否则视为养成材料。
    """

    same_type_keep_best_mode: KeepBestMode = KeepBestMode.SUM
    """留大弃小策略中等级比较的方式：依次比对 / 和值比对 / 概率和值。"""

    redundant_cleanup_enabled: bool = False
    """冗余清理（实验性）总开关；关闭时不产生任何记录与额外操作。"""

    redundant_cleanup_trigger: CleanupTriggerMode = CleanupTriggerMode.SCAN_COMPLETE
    """冗余清理的触发时机：仅在扫描到尾页时 / 所有情况下（含手动停止）。"""

    redundant_action: Action = Action.DEPRECATE
    """对判定为冗余的基质执行的操作（「基质操作规则」中「对于冗余基质」）。"""

    auto_page_flip: bool = True
    """扫描时是否自动翻页"""
    fix_grid_row_offset_after_page_flip: bool = True
    """是否启用翻页后网格行偏移修复（实验性质）"""
    fix_page_flip_overscroll: bool = False
    """是否启用翻页滚动过量修正（实验性质）"""

    update_mirror: str = "github"
    """兼容旧字段：GitHub 下载镜像源。"""
    update_flow: str = DEFAULT_UPDATE_FLOW
    """更新流程：cn_yituliu, cn_mirrorchyan, github。"""
    update_github_mirror: str = "github"
    """GitHub 流程下载镜像源：github, ghproxy, fastgit 等。"""
    update_proxy: str = ""
    """更新代理地址，如 http://127.0.0.1:7890"""
    update_mirrorchyan_res_id: str = ""
    """Mirror 酱资源 ID，由 Mirror 酱后台分配。"""
    update_mirrorchyan_cdk: str = ""
    """Mirror 酱 CDK；日志中不得输出明文。"""
    update_mirrorchyan_user_agent: str = "EER_APP"
    """Mirror 酱来源统计标识。"""

    @model_validator(mode="before")
    @classmethod
    def _normalize_update_fields(cls, data: Any) -> Any:
        """在 v5 内兼容旧更新源字段，不提升配置版本。"""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        legacy_mirror = str(normalized.get("update_mirror") or "")

        if "update_flow" not in normalized:
            if legacy_mirror in LEGACY_FLOW_ALIASES:
                normalized["update_flow"] = LEGACY_FLOW_ALIASES[legacy_mirror]
            else:
                normalized["update_flow"] = DEFAULT_UPDATE_FLOW
        else:
            normalized["update_flow"] = normalize_update_flow(
                str(normalized.get("update_flow") or "")
            )

        if "update_github_mirror" not in normalized:
            normalized["update_github_mirror"] = (
                legacy_mirror if legacy_mirror in MIRRORS else "github"
            )

        # 旧 cn 值自动替换为新流程字段；update_mirror 保持 GitHub 镜像语义。
        if normalized.get("update_mirror") in {YITULIU_FLOW, "cn"}:
            normalized["update_mirror"] = normalized["update_github_mirror"]

        if normalized.get("update_github_mirror") not in MIRRORS:
            normalized["update_github_mirror"] = "github"
        if normalized.get("update_mirror") not in MIRRORS:
            normalized["update_mirror"] = normalized["update_github_mirror"]

        return normalized

    @staticmethod
    def _migrate_v2_to_v3(data: dict) -> None:
        """v2 → v3: 补充 v2 期间新增但未更新版本号的字段"""
        data.setdefault("non_five_star_behavior", "process")
        data.setdefault("auto_page_flip", True)

    @staticmethod
    def _migrate_v3_to_v4(data: dict) -> None:
        """v3 → v4: 添加更新镜像源和代理配置"""
        data.setdefault("update_mirror", "github")
        data.setdefault("update_proxy", "")

    @staticmethod
    def _migrate_v4_to_v5(data: dict) -> None:
        """v4 → v5: 添加 Mirror 酱配置字段。"""
        data.setdefault("update_mirrorchyan_res_id", "")
        data.setdefault("update_mirrorchyan_cdk", "")
        data.setdefault("update_mirrorchyan_user_agent", "EER_APP")
        legacy_mirror = data.get("update_mirror")
        if legacy_mirror == "cn":
            data["update_flow"] = YITULIU_FLOW
            data["update_mirror"] = "github"
            data.setdefault("update_github_mirror", "github")
        elif legacy_mirror in MIRRORS:
            data.setdefault("update_flow", DEFAULT_UPDATE_FLOW)
            data.setdefault("update_github_mirror", legacy_mirror)
        else:
            data.setdefault("update_flow", DEFAULT_UPDATE_FLOW)
            data.setdefault("update_github_mirror", "github")

    @staticmethod
    def _migrate_v5_to_v6(data: dict) -> None:
        """v5 → v6: 添加宝藏匹配方式、仅模式分类开关、同类型数量上限、分组模式和自定义名称。"""
        data.setdefault("treasure_essence_match_mode", "all")
        data.setdefault("high_level_treasure_match_mode", "any")
        data.setdefault("high_level_treasure_sum_threshold", 6)
        data.pop("high_level_treasure_stats", None)
        data.setdefault("high_level_treasure_only_check_attribute", True)
        data.setdefault("high_level_treasure_only_check_secondary", True)
        data.setdefault("high_level_treasure_only_check_skill", True)
        data.setdefault("same_type_treasure_limit_enabled", True)
        data.setdefault("same_type_treasure_limit", 1)
        data.setdefault("same_type_group_mode", "by_weapon")
        data.setdefault("same_type_keep_best", True)
        data.setdefault("fix_grid_row_offset_after_page_flip", True)
        data.setdefault("fix_page_flip_overscroll", False)
        for entry in data.get("treasure_essence_stats", []):
            entry.setdefault("name", "")
            entry.setdefault("no_prompt_switch", False)
        # 非无瑕基质专用的高等级判定设置
        data.setdefault("non_five_star_separate_high_level_settings", False)
        data.setdefault("non_five_star_high_level_attribute_threshold", 3)
        data.setdefault("non_five_star_high_level_secondary_threshold", 3)
        data.setdefault("non_five_star_high_level_skill_threshold", 3)
        data.setdefault("non_five_star_high_level_match_mode", "any")
        data.setdefault("non_five_star_high_level_sum_threshold", 6)
        data.setdefault("non_five_star_high_level_only_check_attribute", True)
        data.setdefault("non_five_star_high_level_only_check_secondary", True)
        data.setdefault("non_five_star_high_level_only_check_skill", True)

    @staticmethod
    def _migrate_v6_to_v7(data: dict) -> None:
        """v6 → v7: 添加留大弃小等级比较方式及非降级原则过滤开关。"""
        data.setdefault("same_type_keep_best_mode", "sum")
        data.setdefault("same_type_non_downgrade_filter", True)

    @staticmethod
    def _migrate_v7_to_v8(data: dict) -> None:
        """v7 → v8: 为自定义宝藏基质补齐稳定 ID。

        补齐顺序即列表顺序，与 profile 中旧格式 `custom_stat_{下标}` 的编号
        一一对应，启动时的 profile 迁移据此把引用改写为 `custom:{id}`。
        """
        seen: set[str] = set()
        for entry in data.get("treasure_essence_stats", []):
            if not isinstance(entry, dict):
                continue
            existing = entry.get("id")
            if not existing or existing in seen:
                entry["id"] = uuid4().hex
            seen.add(entry["id"])

    @staticmethod
    def _migrate_v8_to_v9(data: dict) -> None:
        """v8 → v9: 添加冗余清理（实验性）设置，默认关闭。"""
        data.setdefault("redundant_cleanup_enabled", False)
        data.setdefault("redundant_cleanup_trigger", "scan_complete")
        data.setdefault("redundant_action", "deprecate")

    # 迁移函数映射表：版本号 -> 迁移函数
    # 使用 __func__ 提取底层函数，避免存储 staticmethod 对象（兼容性更好）
    _MIGRATIONS: ClassVar[dict[int, Any]] = {
        2: _migrate_v2_to_v3.__func__,
        3: _migrate_v3_to_v4.__func__,
        4: _migrate_v4_to_v5.__func__,
        5: _migrate_v5_to_v6.__func__,
        6: _migrate_v6_to_v7.__func__,
        7: _migrate_v7_to_v8.__func__,
        8: _migrate_v8_to_v9.__func__,
    }

    @classmethod
    def migrate_from_old_version(cls, old_data: dict) -> UserSetting:
        """从旧版本配置迁移到当前版本

        Args:
            old_data: 旧版本的配置字典

        Returns:
            迁移后的 UserSetting 实例

        Raises:
            ValueError: 如果版本号无效或缺少迁移路径
        """
        old_version = old_data.get("version", 1)

        # 验证版本号有效性
        if old_version < 1:
            raise ValueError(f"无效的配置版本: {old_version}")
        if old_version > cls._VERSION:
            raise ValueError("配置文件版本过高，请更新程序")

        # 链式迁移：逐版本升级
        while old_version < cls._VERSION:
            if old_version not in cls._MIGRATIONS:
                raise ValueError(f"缺少迁移路径: v{old_version} → v{old_version + 1}")
            cls._MIGRATIONS[old_version](old_data)
            old_version += 1

        # 更新版本号
        old_data["version"] = cls._VERSION

        # 验证并返回
        return cls.model_validate(old_data)

    def update_from_model(self, other: UserSetting) -> None:
        for field in self.__class__.model_fields:
            setattr(self, field, getattr(other, field))

    def update_from_dict(self, data: dict[str, Any]) -> None:
        model = UserSetting.model_validate(data)
        self.update_from_model(model)
