"""Layer 2：认领决策——决定哪把武器接受当前基质。

本模块是纯逻辑（不写 profile），但维护扫描批次内的累加状态（ClaimContext）。
ClaimContext 在扫描开始时创建，扫描期间每枚基质调用 claim()，扫描结束后
由 engine 读取 ClaimResult 同步状态。
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Literal

from loguru import logger

from endfield_essence_recognizer.core.scanner.classifier import (
    _format_stat_key,
)
from endfield_essence_recognizer.core.scanner.evaluate import (
    _group_stat_key,
    _level_cmp,
    _normalize_by_stat_type,
    _order_candidate_ids,
)
from endfield_essence_recognizer.core.scanner.models import (
    ClaimKind,
    ClaimResult,
    ClassificationResult,
    EssenceData,
    EssenceQuality,
    LevelTuple,
    RejectReason,
)
from endfield_essence_recognizer.schemas.profile import CUSTOM_ID_PREFIX
from endfield_essence_recognizer.schemas.user_setting import (
    KeepBestMode,
    SameTypeGroupMode,
    UserSetting,
)

if TYPE_CHECKING:
    from endfield_essence_recognizer.game_data.models.v2 import StatType
    from endfield_essence_recognizer.game_data.static_game_data import StaticGameData

# 数量上限关闭时的占位上限
UNLIMITED_LIMIT = 999


class ClaimContext:
    """扫描批次级的认领上下文——替代模块级全局状态和 UserSetting._same_type_* 字段。

    在扫描开始时创建，扫描期间每枚基质调用 claim()，扫描结束后由 engine
    读取 group_scanned_counts 等数据用于展示。
    """

    def __init__(
        self,
        profile_entries: list,
        user_setting: UserSetting,
        static_game_data: StaticGameData | None = None,
    ) -> None:
        """从 profile 初始化最佳等级、计数、相等跳过名额。

        Args:
            profile_entries: profile.treasure_matrix 条目列表。
            user_setting: 用户设置（用于读取自定义基质配置）。
            static_game_data: 静态游戏数据。
        """
        # 最佳等级、计数、相等跳过名额（按 key 索引，key 可以是 weapon_id 或 stat_key）
        self.best_levels: dict[str | tuple, LevelTuple] = {}
        self.treasure_counts: dict[str | tuple, int] = {}
        self.equal_skips: dict[str | tuple, int] = {}

        # 日志显示用引用
        self._static_game_data = static_game_data
        self._user_setting = user_setting

        # 本轮扫描中的累加状态
        self.claimed_this_scan: set[tuple[str, LevelTuple]] = set()
        self.group_scanned: dict[tuple, int] = {}

        # 从 profile 初始化
        self._init_from_profile(profile_entries, user_setting, static_game_data)

    def _display(self, key: str | tuple) -> str:
        """输出 "中文名(id)" 格式便于日志排查；属性组合输出可读名称。"""
        from endfield_essence_recognizer.core.scanner.classifier import (
            _custom_stat_display,
        )

        if isinstance(key, tuple):
            return _format_stat_key(key, self._static_game_data)
        if key.startswith(CUSTOM_ID_PREFIX):
            custom = _custom_stat_display(self._user_setting, key)
            return f"{custom}({key})" if custom else key
        weapon = (
            self._static_game_data.get_weapon(key) if self._static_game_data else None
        )
        if weapon:
            return f"{weapon.name}({key})"
        return key

    def _init_from_profile(
        self,
        profile_entries: list,
        user_setting: UserSetting,
        static_game_data: StaticGameData | None,
    ) -> None:
        """从 profile 的宝藏基质配置中初始化同类型最佳等级、相等跳过名额与存量计数。"""
        from endfield_essence_recognizer.schemas.profile import CUSTOM_ID_PREFIX

        # 自定义基质条目的属性组合
        custom_stat_key_by_id: dict[str, tuple[str | None, ...]] = {
            f"{CUSTOM_ID_PREFIX}{ts.id}": (ts.attribute, ts.secondary, ts.skill)
            for ts in user_setting.treasure_essence_stats
            if ts.id
        }

        # 按分组键收集已保存的等级
        group_levels: dict[str | tuple, list[LevelTuple]] = {}
        for entry in profile_entries:
            levels: LevelTuple = (
                entry.affix1_level,
                entry.affix2_level,
                entry.affix3_level,
            )
            weapon_id = entry.weapon_id
            group_levels.setdefault(weapon_id, []).append(levels)
            stat_key = custom_stat_key_by_id.get(weapon_id)
            if stat_key is None:
                weapon = (
                    static_game_data.get_weapon(weapon_id) if static_game_data else None
                )
                if weapon:
                    stat_key = (
                        weapon.stat1_id,
                        weapon.stat2_id,
                        weapon.stat3_id,
                    )
            if stat_key is not None:
                group_levels.setdefault(stat_key, []).append(levels)

        # 每组以最高等级作为阈值，并以等于该阈值的数量作为相等跳过名额
        mode = user_setting.same_type_keep_best_mode

        for key, levels_list in group_levels.items():
            stat_types = self._get_stat_types(key, static_game_data)
            best = max(
                levels_list,
                key=functools.cmp_to_key(
                    lambda a, b, _mode=mode, _stat_types=stat_types: _level_cmp(
                        a, b, _mode, _stat_types
                    )
                ),
            )
            self.best_levels[key] = best
            self.equal_skips[key] = sum(1 for lv in levels_list if lv == best)
            self.treasure_counts[key] = len(levels_list)

    def _get_stat_types(
        self, key: str | tuple, static_game_data: StaticGameData | None
    ) -> list[StatType | None] | None:
        """根据 key 获取词条类型列表。"""
        if isinstance(key, tuple) and len(key) == 3:
            stat_types = []
            for stat_id in key:
                if stat_id is None:
                    stat_types.append(None)
                else:
                    stat_info = (
                        static_game_data.get_stat(stat_id) if static_game_data else None
                    )
                    stat_types.append(stat_info.type if stat_info else None)
            return stat_types
        return None

    def reset_scan(self) -> None:
        """新一轮扫描开始时清空累加状态。"""
        self.claimed_this_scan.clear()
        self.group_scanned.clear()

    def get_group_scanned_counts(self) -> dict[tuple, int]:
        """获取每个属性组合扫描到的匹配基质枚数（展示用）。"""
        return self.group_scanned.copy()

    def _record_group_scanned(
        self,
        matched_weapon_ids: set[str],
        setting: UserSetting,
        static_game_data: StaticGameData | None,
    ) -> None:
        """记录组扫描计数（与认领正交，供展示用）。"""
        matched = matched_weapon_ids - set(setting.trash_weapon_ids)
        if (
            matched
            and static_game_data
            and any(static_game_data.get_weapon(wid) for wid in matched)
        ):
            key = _group_stat_key(matched, static_game_data)
            self.group_scanned[key] = self.group_scanned.get(key, 0) + 1

    def claim(
        self,
        classification: ClassificationResult,
        data: EssenceData,
        setting: UserSetting,
        weapon_essence_levels: dict[str, LevelTuple] | None = None,
        weapon_priority_order: list[str] | None = None,
        static_game_data: StaticGameData | None = None,
    ) -> ClaimResult:
        """对单枚基质做出认领决策。纯逻辑，不写 profile。

        Args:
            classification: Layer 1 的分类结果。
            data: 原始识别数据。
            setting: 用户设置。
            weapon_essence_levels: 各武器当前基质等级（用于非降级原则）。
            weapon_priority_order: 武器优先级排序。
            static_game_data: 静态游戏数据。

        Returns:
            ClaimResult，包含认领决策和状态变更。
        """
        # 非宝藏基质不认领
        if classification.quality != EssenceQuality.TREASURE:
            return ClaimResult()

        # 记录组扫描计数
        if classification.matched_weapon_ids:
            self._record_group_scanned(
                classification.matched_weapon_ids, setting, static_game_data
            )

        # 归一化为语义顺序（属性、副属性、技能），与武器 stat1/2/3、profile affix1/2/3 对齐
        stat_key, stat_types, current_levels = _normalize_by_stat_type(
            data.stats, data.stat_types, data.levels
        )
        matched_weapon_ids = classification.matched_weapon_ids

        # 数量上限关闭
        if not setting.same_type_treasure_limit_enabled:
            if matched_weapon_ids:
                return self._claim_by_weapon(
                    classification,
                    matched_weapon_ids,
                    current_levels,
                    limit=UNLIMITED_LIMIT,
                    keep_best=setting.same_type_keep_best,
                    mode=setting.same_type_keep_best_mode,
                    stat_types=stat_types,
                    weapon_essence_levels=weapon_essence_levels,
                    weapon_priority_order=weapon_priority_order,
                    static_game_data=static_game_data,
                    exhausted_policy="keep",
                    limit_off=True,
                    setting=setting,
                )
            return ClaimResult()

        limit = setting.same_type_treasure_limit
        keep_best = setting.same_type_keep_best
        mode = setting.same_type_keep_best_mode

        if (
            setting.same_type_group_mode == SameTypeGroupMode.BY_WEAPON
            and matched_weapon_ids
        ):
            return self._claim_by_weapon(
                classification,
                matched_weapon_ids,
                current_levels,
                limit,
                keep_best,
                mode,
                stat_types,
                weapon_essence_levels,
                weapon_priority_order,
                static_game_data,
                setting=setting,
            )

        # 默认按基质分组
        return self._claim_by_matrix(
            classification,
            stat_key,
            current_levels,
            limit,
            keep_best,
            mode,
            stat_types,
            matched_weapon_ids,
            weapon_essence_levels,
            weapon_priority_order,
            static_game_data,
            setting,
        )

    def _claim_by_weapon(
        self,
        classification: ClassificationResult,
        matched_weapon_ids: set[str],
        current_levels: LevelTuple,
        limit: int,
        keep_best: bool,
        mode: KeepBestMode,
        stat_types: list[StatType | None],
        weapon_essence_levels: dict[str, LevelTuple] | None,
        weapon_priority_order: list[str] | None,
        static_game_data: StaticGameData | None,
        exhausted_policy: Literal["trash", "keep"] = "trash",
        limit_off: bool = False,
        setting: UserSetting | None = None,
    ) -> ClaimResult:
        """按武器分组的认领逻辑。"""
        weapon_ids = _order_candidate_ids(matched_weapon_ids, weapon_priority_order)

        # 非降级原则过滤
        if weapon_essence_levels and setting and setting.same_type_non_downgrade_filter:
            upgradeable_ids = []
            for wid in weapon_ids:
                existing = weapon_essence_levels.get(wid)
                if existing is None:
                    upgradeable_ids.append(wid)
                elif (
                    current_levels[0] >= existing[0]
                    and current_levels[1] >= existing[1]
                    and current_levels[2] >= existing[2]
                ):
                    upgradeable_ids.append(wid)
                else:
                    logger.debug(
                        f"[非降级] 武器 {self._display(wid)} 已保存等级 {existing}，"
                        f"基质等级 {current_levels}，不满足非降级原则，过滤"
                    )
            weapon_ids = upgradeable_ids

        if not weapon_ids:
            if exhausted_policy == "keep":
                logger.debug("[非降级] 所有匹配武器均不满足非降级原则，保留（不落盘）")
                return ClaimResult()
            return ClaimResult(reject_reason=RejectReason.NON_DOWNGRADE)

        # 相同等级命中统一路径：不分散升级其他武器
        identical_result = self._claim_identical_level(
            weapon_ids,
            current_levels,
            limit,
            mode,
            stat_types,
            static_game_data,
        )
        if identical_result is not None:
            return identical_result

        # 数量上限关闭路径
        if limit_off:
            return self._claim_limit_off(
                weapon_ids,
                matched_weapon_ids,
                current_levels,
                mode,
                stat_types,
                keep_best,
                static_game_data,
            )

        # 数量上限开启路径
        return self._claim_limit_on(
            weapon_ids,
            current_levels,
            limit,
            keep_best,
            mode,
            stat_types,
            exhausted_policy,
            static_game_data,
        )

    def _claim_identical_level(
        self,
        weapon_ids: list[str],
        current_levels: LevelTuple,
        limit: int,
        mode: KeepBestMode,
        stat_types: list[StatType | None],
        static_game_data: StaticGameData | None,
    ) -> ClaimResult | None:
        """相同等级命中（组内已有武器记录了该等级）：不再分散给其他武器。

        同一枚物理基质被重复评估（UI 未刷新/翻页重叠）时，若不拦截会把
        同等级的下一把武器误升级落盘，永久污染 profile。这里统一处理：

        ① 存量跳过：消耗已记录基质的相等跳过名额（重扫存量，不计数不落盘）；
        ② 组内空槽：把认领给优先序中第一把还没有记录的武器（孪生武器不饿死）；
        ③ 无空槽：判定为宝藏、不落盘（占用该武器限额名额；全部满额则养成材料）。

        Returns:
            已处理的 ClaimResult；组内没有同等级记录时返回 None（走常规认领）。
        """
        identical_wids = [
            wid for wid in weapon_ids if self.best_levels.get(wid) == current_levels
        ]
        if not identical_wids:
            return None

        # ① 存量跳过：重扫已记录的同等级基质
        for wid in identical_wids:
            skip = self.equal_skips.get(wid, 0)
            if skip > 0:
                self.equal_skips[wid] = skip - 1
                logger.debug(
                    f"[相同等级] 武器 {self._display(wid)} 已记录等级 {current_levels}，"
                    f"消耗存量跳过名额（剩余 {skip - 1}），不重复认领"
                )
                return ClaimResult(
                    updated_levels={wid: current_levels},
                    claim_kind=ClaimKind.SKIP_EXISTING,
                    owner_key=wid,
                )

        # ② 组内空槽：优先序中第一把无记录的武器认领落盘（孪生武器不饿死）
        for wid in weapon_ids:
            if self.best_levels.get(wid) is None:
                self.best_levels[wid] = current_levels
                self.treasure_counts[wid] = 1
                self.claimed_this_scan.add((wid, current_levels))
                logger.debug(
                    f"[相同等级] 武器 {self._display(wid)} 无记录，认领基质等级 {current_levels}"
                )
                return ClaimResult(
                    accepted_weapon_id=wid,
                    updated_levels={wid: current_levels},
                    claim_kind=ClaimKind.NEW_SLOT,
                    owner_key=wid,
                )

        # ③ 无空槽：判定宝藏、不落盘（占用该武器限额名额）
        for wid in weapon_ids:
            if self.treasure_counts.get(wid, 0) < limit:
                self.treasure_counts[wid] = self.treasure_counts.get(wid, 0) + 1
                logger.debug(
                    f"[相同等级] 武器 {self._display(wid)} 已持有同等级基质，"
                    f"保留为宝藏（仅计数，不落盘），当前计数 "
                    f"{self.treasure_counts[wid]}"
                )
                return ClaimResult(
                    accepted_weapon_id=wid,
                    updated_levels={wid: self.best_levels[wid]},
                    claim_kind=ClaimKind.COUNT_ONLY,
                    owner_key=wid,
                )

        # 全部满额：与限额语义一致，标记为养成材料
        current_count = max(
            (self.treasure_counts.get(w, 0) for w in weapon_ids),
            default=0,
        )
        logger.debug("[相同等级] 所有匹配武器均已达上限，标记为养成材料")
        return ClaimResult(
            reject_reason=RejectReason.LIMIT,
            current_count=current_count,
        )

    def _claim_limit_off(
        self,
        weapon_ids: list[str],
        matched_weapon_ids: set[str],
        current_levels: LevelTuple,
        mode: KeepBestMode,
        stat_types: list[StatType | None],
        keep_best: bool,
        static_game_data: StaticGameData | None,
    ) -> ClaimResult:
        """数量上限关闭：单武器认领，相同等级命中已由 _claim_identical_level 处理。"""
        group_stat_key = _group_stat_key(matched_weapon_ids, static_game_data)

        for i, weapon_id in enumerate(weapon_ids):
            old_best = self.best_levels.get(weapon_id)
            if (
                old_best is not None
                and _level_cmp(current_levels, old_best, mode, stat_types) <= 0
            ):
                logger.debug(
                    f"[数量上限关闭] 武器 {self._display(weapon_id)} 已持有 "
                    f"{old_best}（不差于当前 {current_levels}），分散给下一把武器"
                )
                continue
            if old_best is None:
                self.treasure_counts[weapon_id] = (
                    self.treasure_counts.get(weapon_id, 0) + 1
                )
            self.best_levels[weapon_id] = current_levels
            self.claimed_this_scan.add((weapon_id, current_levels))
            logger.debug(
                f"[数量上限关闭] 武器 {self._display(weapon_id)} 认领基质等级 {current_levels}"
            )
            # 升级：释放旧等级级联
            cascade: dict[str, LevelTuple] = {}
            if old_best is not None and (weapon_id, old_best) in self.claimed_this_scan:
                remaining = weapon_ids[i + 1 :]
                if remaining:
                    cascade = self._cascade_freed(
                        old_best,
                        remaining,
                        UNLIMITED_LIMIT,
                        mode,
                        stat_types,
                    )
            return ClaimResult(
                accepted_weapon_id=weapon_id,
                updated_levels={weapon_id: current_levels},
                cascade_updated=cascade,
                group_stat_key=group_stat_key,
                claim_kind=(
                    ClaimKind.UPGRADE if old_best is not None else ClaimKind.NEW_SLOT
                ),
                owner_key=weapon_id,
                released_levels=old_best,
            )

        # 无人可认领
        if keep_best and all(
            self.best_levels.get(w) is not None
            and _level_cmp(current_levels, self.best_levels[w], mode, stat_types) < 0
            for w in weapon_ids
        ):
            logger.debug(
                "[数量上限关闭] 所有匹配武器均持有更佳等级，留大弃小开启，跳过"
            )
            return ClaimResult(group_stat_key=group_stat_key)

        # 仅计数（等级不变/留大弃小关闭时的更差基质）：同步既有等级与计数
        target = weapon_ids[0]
        self.treasure_counts[target] = self.treasure_counts.get(target, 0) + 1
        self.claimed_this_scan.add((target, current_levels))
        logger.debug(f"[数量上限关闭] 武器 {self._display(target)} 仅计数")
        return ClaimResult(
            accepted_weapon_id=target,
            updated_levels={target: self.best_levels.get(target) or current_levels},
            group_stat_key=group_stat_key,
            claim_kind=ClaimKind.COUNT_ONLY,
            owner_key=target,
        )

    def _claim_limit_on(
        self,
        weapon_ids: list[str],
        current_levels: LevelTuple,
        limit: int,
        keep_best: bool,
        mode: KeepBestMode,
        stat_types: list[StatType | None],
        exhausted_policy: Literal["trash", "keep"],
        static_game_data: StaticGameData | None,
    ) -> ClaimResult:
        """数量上限开启：按武器逐个尝试认领（相同等级已由 _claim_identical_level 处理）。"""
        rejected_by_worse_level = False

        for i, weapon_id in enumerate(weapon_ids):
            old_best = self.best_levels.get(weapon_id)

            # 留大弃小
            if keep_best and self._try_keep_best(
                weapon_id, current_levels, mode, stat_types
            ):
                if old_best is not None and old_best != current_levels:
                    self.claimed_this_scan.add((weapon_id, current_levels))
                    cascade: dict[str, LevelTuple] = {}
                    if (weapon_id, old_best) in self.claimed_this_scan:
                        remaining = weapon_ids[i + 1 :]
                        if remaining:
                            cascade = self._cascade_freed(
                                old_best,
                                remaining,
                                limit,
                                mode,
                                stat_types,
                            )
                    return ClaimResult(
                        accepted_weapon_id=weapon_id,
                        updated_levels={weapon_id: current_levels},
                        cascade_updated=cascade,
                        claim_kind=ClaimKind.UPGRADE,
                        owner_key=weapon_id,
                        released_levels=old_best,
                    )
                return ClaimResult(
                    accepted_weapon_id=weapon_id,
                    updated_levels={weapon_id: current_levels},
                    claim_kind=ClaimKind.SKIP_EXISTING,
                    owner_key=weapon_id,
                )

            # 数量上限认领
            if self._try_claim_slot(
                weapon_id, current_levels, limit, keep_best, mode, stat_types
            ):
                self.claimed_this_scan.add((weapon_id, current_levels))
                return ClaimResult(
                    accepted_weapon_id=weapon_id,
                    updated_levels={weapon_id: current_levels},
                    claim_kind=ClaimKind.NEW_SLOT,
                    owner_key=weapon_id,
                )

            # 未被认领：判断拒绝原因
            if keep_best and self.treasure_counts.get(weapon_id, 0) < limit:
                rejected_by_worse_level = True

        # 所有武器都已达上限
        if exhausted_policy == "keep":
            logger.debug("[数量上限] 所有可选武器均已认领 1 枚，保留（不落盘）")
            return ClaimResult()

        current_count = max(
            (self.treasure_counts.get(w, 0) for w in weapon_ids),
            default=0,
        )
        if rejected_by_worse_level:
            return ClaimResult(
                reject_reason=RejectReason.WORSE_LEVEL,
                current_count=current_count,
            )

        return ClaimResult(
            reject_reason=RejectReason.LIMIT,
            current_count=current_count,
        )

    def _try_keep_best(
        self,
        key: str | tuple,
        current_levels: LevelTuple,
        mode: KeepBestMode,
        stat_types: list[StatType | None] | None,
    ) -> bool:
        """留大弃小：判断当前基质是否属于该组"已保存"的那一枚（或其升级版）。"""
        best = self.best_levels.get(key)
        if best is None:
            return False

        cmp = _level_cmp(current_levels, best, mode, stat_types)
        if cmp > 0:
            self.best_levels[key] = current_levels
            logger.debug(
                f"[留大弃小] {self._display(key)} 基质等级 {current_levels} "
                f"优于已保存 {best}，认领并提升阈值"
            )
            skip = self.equal_skips.get(key, 0)
            if skip > 0:
                self.equal_skips[key] = skip - 1
            return True
        if cmp == 0:
            skip = self.equal_skips.get(key, 0)
            if skip > 0:
                self.equal_skips[key] = skip - 1
                logger.debug(
                    f"[留大弃小] {self._display(key)} 基质等级 {current_levels} "
                    f"等于已保存 {best}，认领"
                )
                return True
        return False

    def _try_claim_slot(
        self,
        key: str | tuple,
        current_levels: LevelTuple,
        limit: int,
        keep_best: bool,
        mode: KeepBestMode,
        stat_types: list[StatType | None] | None,
    ) -> bool:
        """按数量上限认领：未达上限则保留并计数。"""
        count = self.treasure_counts.get(key, 0)
        if count >= limit:
            return False
        best = self.best_levels.get(key)
        if (
            keep_best
            and best is not None
            and _level_cmp(current_levels, best, mode, stat_types) < 0
        ):
            logger.debug(
                f"[数量上限] {self._display(key)} 基质等级 {current_levels} 劣于已保存 {best}，不认领"
            )
            return False
        self.treasure_counts[key] = count + 1
        if best is None or _level_cmp(current_levels, best, mode, stat_types) > 0:
            self.best_levels[key] = current_levels
        logger.debug(
            f"[数量上限] {self._display(key)} 认领基质等级 {current_levels}，当前计数 {count + 1}/{limit}"
        )
        return True

    def _cascade_freed(
        self,
        freed_levels: LevelTuple,
        remaining_ids: list[str],
        limit: int,
        mode: KeepBestMode,
        stat_types: list[StatType | None] | None,
    ) -> dict[str, LevelTuple]:
        """级联：将释放的旧等级分配给剩余武器。返回实际级联的武器等级映射。"""
        result: dict[str, LevelTuple] = {}
        for wid in remaining_ids:
            if self.treasure_counts.get(wid, 0) >= limit:
                continue
            old_best = self.best_levels.get(wid)
            if (
                old_best is not None
                and _level_cmp(freed_levels, old_best, mode, stat_types) <= 0
            ):
                continue
            self.best_levels[wid] = freed_levels
            self.treasure_counts[wid] = self.treasure_counts.get(wid, 0) + 1
            result[wid] = freed_levels
            logger.debug(
                f"[级联] 武器 {self._display(wid)} 认领释放的等级 {freed_levels}"
            )
            break
        return result

    def _claim_by_matrix(
        self,
        classification: ClassificationResult,
        stat_key: tuple[str | None, ...],
        current_levels: LevelTuple,
        limit: int,
        keep_best: bool,
        mode: KeepBestMode,
        stat_types: list[StatType | None],
        matched_weapon_ids: set[str] | None,
        weapon_essence_levels: dict[str, LevelTuple] | None,
        weapon_priority_order: list[str] | None,
        static_game_data: StaticGameData | None,
        setting: UserSetting,
    ) -> ClaimResult:
        """按基质分组（属性组合共享计数）的认领逻辑。"""
        stat_label = _format_stat_key(stat_key, static_game_data)

        if not matched_weapon_ids:
            # 留大弃小优先于数量上限：更优基质替换组内已保存的那一枚（替换语义，不增计数）
            if keep_best and self._try_keep_best(
                stat_key, current_levels, mode, stat_types
            ):
                return ClaimResult(
                    claim_kind=ClaimKind.UPGRADE,
                    owner_key=stat_key,
                )

            # 数量上限：未达上限则新增并计数
            if self._try_claim_slot(
                stat_key, current_levels, limit, keep_best, mode, stat_types
            ):
                return ClaimResult(
                    claim_kind=ClaimKind.NEW_SLOT,
                    owner_key=stat_key,
                )

            # 未被认领：未达上限说明是被留大弃小拦下的更差基质
            count = self.treasure_counts.get(stat_key, 0)
            if keep_best and count < limit:
                return ClaimResult(reject_reason=RejectReason.WORSE_LEVEL)
            logger.debug(f"[数量上限] 属性组合 [{stat_label}] 已达上限 {count}/{limit}")
            return ClaimResult(
                reject_reason=RejectReason.LIMIT,
                current_count=count,
            )

        weapon_ids = _order_candidate_ids(matched_weapon_ids, weapon_priority_order)

        # 非降级原则过滤
        if weapon_essence_levels and setting.same_type_non_downgrade_filter:
            upgradeable_ids = []
            for wid in weapon_ids:
                existing = weapon_essence_levels.get(wid)
                if existing is None:
                    upgradeable_ids.append(wid)
                elif (
                    current_levels[0] >= existing[0]
                    and current_levels[1] >= existing[1]
                    and current_levels[2] >= existing[2]
                ):
                    upgradeable_ids.append(wid)
            weapon_ids = upgradeable_ids

        if not weapon_ids:
            return ClaimResult(reject_reason=RejectReason.NON_DOWNGRADE)

        count = self.treasure_counts.get(stat_key, 0)

        for weapon_id in weapon_ids:
            if keep_best:
                best = self.best_levels.get(weapon_id)
                if (
                    best is not None
                    and _level_cmp(current_levels, best, mode, stat_types) == 0
                ):
                    skip = self.equal_skips.get(weapon_id, 0)
                    if skip > 0:
                        self.equal_skips[weapon_id] = skip - 1
                        return ClaimResult(
                            accepted_weapon_id=weapon_id,
                            claim_kind=ClaimKind.SKIP_EXISTING,
                            owner_key=stat_key,
                        )
                if (
                    best is not None
                    and _level_cmp(current_levels, best, mode, stat_types) > 0
                ):
                    self.best_levels[weapon_id] = current_levels
                    return ClaimResult(
                        accepted_weapon_id=weapon_id,
                        updated_levels={weapon_id: current_levels},
                        claim_kind=ClaimKind.UPGRADE,
                        owner_key=stat_key,
                        released_levels=best,
                    )

            if count < limit:
                best = self.best_levels.get(weapon_id)
                if (
                    keep_best
                    and best is not None
                    and _level_cmp(current_levels, best, mode, stat_types) < 0
                ):
                    continue
                self.treasure_counts[stat_key] = count + 1
                self.treasure_counts[weapon_id] = (
                    self.treasure_counts.get(weapon_id, 0) + 1
                )
                best = self.best_levels.get(weapon_id)
                if (
                    best is None
                    or _level_cmp(current_levels, best, mode, stat_types) > 0
                ):
                    self.best_levels[weapon_id] = current_levels
                return ClaimResult(
                    accepted_weapon_id=weapon_id,
                    updated_levels={weapon_id: current_levels},
                    claim_kind=ClaimKind.NEW_SLOT,
                    owner_key=stat_key,
                )

        # 虚拟武器
        for v_idx in range(count + 1):
            virtual_key = f"_virtual_{stat_key}_{v_idx}"
            if v_idx < count:
                if keep_best:
                    best = self.best_levels.get(virtual_key)
                    if best is not None:
                        cmp = _level_cmp(current_levels, best, mode, stat_types)
                        if cmp == 0:
                            continue
                        if cmp > 0:
                            self.best_levels[virtual_key] = current_levels
                            return ClaimResult()
                continue
            if count >= limit:
                break
            self.treasure_counts[stat_key] = count + 1
            self.best_levels[virtual_key] = current_levels
            return ClaimResult(
                claim_kind=ClaimKind.VIRTUAL_SLOT,
                owner_key=stat_key,
            )

        return ClaimResult(
            reject_reason=RejectReason.LIMIT,
            current_count=count,
        )
