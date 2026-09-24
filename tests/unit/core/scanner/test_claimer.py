"""Tests for Layer 2: claimer.py — claiming logic and ClaimContext."""

from unittest.mock import MagicMock

import pytest

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
    RarityLabel,
)
from endfield_essence_recognizer.core.scanner.claimer import ClaimContext
from endfield_essence_recognizer.core.scanner.classifier import classify_essence
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    RejectReason,
)
from endfield_essence_recognizer.game_data.models.v2 import EssenceStatV2, StatType
from endfield_essence_recognizer.schemas.user_setting import (
    KeepBestMode,
    SameTypeGroupMode,
    UserSetting,
)


def _make_stat(stat_id: str, stat_type: StatType) -> EssenceStatV2:
    return EssenceStatV2(stat_id=stat_id, name=stat_id, type=stat_type)


_STAT_A = _make_stat("A", StatType.ATTRIBUTE)
_STAT_B = _make_stat("B", StatType.SECONDARY)
_STAT_C = _make_stat("C", StatType.SKILL)

_MOCK_STAT_TABLE: dict[str, EssenceStatV2] = {
    "A": _STAT_A,
    "B": _STAT_B,
    "C": _STAT_C,
}


@pytest.fixture
def mock_static_game_data():
    mock_data = MagicMock()
    mock_data.get_stat.side_effect = lambda sid: _MOCK_STAT_TABLE.get(sid)
    mock_data.find_weapons_by_stats.return_value = []
    mock_data.get_weapon.return_value = None
    mock_data.get_weapon_type.return_value = None
    return mock_data


@pytest.fixture
def default_settings():
    return UserSetting()


@pytest.fixture
def default_essence_data():
    return EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[6, 6, 3],
        rarity=RarityLabel.FIVE,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )


@pytest.fixture
def claim_context():
    return ClaimContext([], UserSetting())


def _make_weapon(name: str, weapon_id: str, stat1: str, stat2: str, stat3: str):
    weapon = MagicMock()
    weapon.name = name
    weapon.weapon_id = weapon_id
    weapon.stat1_id = stat1
    weapon.stat2_id = stat2
    weapon.stat3_id = stat3
    weapon.rarity = 5
    weapon.weapon_type = "sword"
    return weapon


class TestClaimByWeapon:
    """按武器分组的认领逻辑测试。"""

    def test_claim_first_essence(
        self,
        mock_static_game_data,
        default_settings,
        default_essence_data,
        claim_context,
    ):
        """第一枚基质应该被认领。"""
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_001"]
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON

        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        result = claim_context.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.accepted_weapon_id == "wpn_001"
        assert result.reject_reason is None

    def test_claim_second_same_type_rejected_by_limit(
        self,
        mock_static_game_data,
        default_settings,
        default_essence_data,
        claim_context,
    ):
        """第二枚同类型基质应该被数量上限拒绝。"""
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_001"]
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = False

        # 第一枚
        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        claim_context.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        # 第二枚（相同等级）
        result = claim_context.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.reject_reason == RejectReason.LIMIT

    def test_claim_upgrade_replaces(
        self, mock_static_game_data, default_settings, claim_context
    ):
        """更高等级的基质应该替换旧的。"""
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_001"]
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = True
        default_settings.same_type_keep_best_mode = KeepBestMode.SUM

        # 低等级
        low_essence = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[3, 3, 1],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        classification = classify_essence(
            low_essence, default_settings, mock_static_game_data
        )
        claim_context.claim(
            classification,
            low_essence,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        # 高等级
        high_essence = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[6, 6, 3],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        classification = classify_essence(
            high_essence, default_settings, mock_static_game_data
        )
        result = claim_context.claim(
            classification,
            high_essence,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.accepted_weapon_id == "wpn_001"
        assert "wpn_001" in result.updated_levels


class TestClaimByMatrix:
    """按基质分组的认领逻辑测试。"""

    def test_claim_first_essence(
        self,
        mock_static_game_data,
        default_settings,
        default_essence_data,
        claim_context,
    ):
        """第一枚基质应该被认领。"""
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_001"]
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_STAT

        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        result = claim_context.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.accepted_weapon_id == "wpn_001"
        assert result.reject_reason is None

    def test_claim_limit_off_single_claim(
        self, mock_static_game_data, default_settings, claim_context
    ):
        """数量上限关闭：每枚基质只认领一把武器。"""
        mock_static_game_data.find_weapons_by_stats.return_value = [
            "wpn_001",
            "wpn_002",
        ]
        default_settings.same_type_treasure_limit_enabled = False
        default_settings.same_type_keep_best = False

        essence = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[6, 6, 3],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        classification = classify_essence(
            essence, default_settings, mock_static_game_data
        )
        result = claim_context.claim(
            classification,
            essence,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        # 只认领一把武器
        assert result.accepted_weapon_id is not None
        assert result.reject_reason is None


class TestClaimUnmatchedHighLevel:
    """不匹配任何已实装武器的高等级宝藏基质（按属性组合分组认领）。"""

    @pytest.fixture
    def high_level_settings(self, default_settings):
        default_settings.high_level_treasure_enabled = True
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = True
        default_settings.same_type_keep_best_mode = KeepBestMode.WEIGHTED_SUM
        return default_settings

    def _make_essence(self, levels, stats=None, stat_types=None) -> EssenceData:
        return EssenceData(
            stats=stats or ["A", "B", "C"],
            stat_types=stat_types
            or [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=levels,
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )

    def _claim(self, ctx, essence, settings, static_data):
        classification = classify_essence(essence, settings, static_data)
        assert classification.quality == EssenceQuality.TREASURE
        return ctx.claim(
            classification, essence, settings, static_game_data=static_data
        )

    def test_better_level_replaces_after_limit_reached(
        self, mock_static_game_data, high_level_settings, claim_context
    ):
        """达到数量上限后，更优基质仍应按留大弃小替换（上游 issue #199）。"""
        first = self._claim(
            claim_context,
            self._make_essence([3, 1, 1]),
            high_level_settings,
            mock_static_game_data,
        )
        second = self._claim(
            claim_context,
            self._make_essence([4, 1, 1]),
            high_level_settings,
            mock_static_game_data,
        )

        assert first.reject_reason is None
        assert second.reject_reason is None
        assert claim_context.best_levels[("A", "B", "C")] == (4, 1, 1)
        # 替换语义：不额外占用名额
        assert claim_context.treasure_counts[("A", "B", "C")] == 1

    def test_worse_level_rejected_after_limit_reached(
        self, mock_static_game_data, high_level_settings, claim_context
    ):
        """扫描顺序反转：更差基质仍判为养成材料，保留的始终是更优的那枚。"""
        self._claim(
            claim_context,
            self._make_essence([4, 1, 1]),
            high_level_settings,
            mock_static_game_data,
        )
        second = self._claim(
            claim_context,
            self._make_essence([3, 1, 1]),
            high_level_settings,
            mock_static_game_data,
        )

        assert second.reject_reason is RejectReason.LIMIT
        assert claim_context.best_levels[("A", "B", "C")] == (4, 1, 1)
        assert claim_context.treasure_counts[("A", "B", "C")] == 1

    def test_stat_order_normalized_into_same_group(
        self, mock_static_game_data, high_level_settings, claim_context
    ):
        """词条显示顺序不同的同属性组合归入同一分组，不各占名额。"""
        self._claim(
            claim_context,
            self._make_essence([3, 1, 1]),
            high_level_settings,
            mock_static_game_data,
        )
        # 同一属性组合，识别位置顺序为技能、属性、副属性
        reordered = self._make_essence(
            [1, 4, 1],
            stats=["C", "A", "B"],
            stat_types=[StatType.SKILL, StatType.ATTRIBUTE, StatType.SECONDARY],
        )
        second = self._claim(
            claim_context, reordered, high_level_settings, mock_static_game_data
        )

        assert list(claim_context.treasure_counts) == [("A", "B", "C")]
        assert second.reject_reason is None
        assert claim_context.best_levels[("A", "B", "C")] == (4, 1, 1)


class TestClaimNonTreasure:
    """非宝藏基质不认领。"""

    def test_trash_not_claimed(
        self, mock_static_game_data, default_settings, claim_context
    ):
        """TRASH 基质不认领。"""
        from endfield_essence_recognizer.core.scanner.models import ClassificationResult

        classification = ClassificationResult(quality=EssenceQuality.TRASH)
        essence = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[0, 0, 0],
            rarity=RarityLabel.OTHER,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        result = claim_context.claim(
            classification,
            essence,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.accepted_weapon_id is None
        assert result.reject_reason is None


class TestClaimIdenticalLevel:
    """相同等级命中：不分散升级其他武器（幽灵升级修复）。"""

    def _make_context_with_profile(self, entries, settings, static_data):
        """用 profile 条目构造 ClaimContext（含静态武器数据用于 stat_key 解析）。"""

        def _get_weapon(wid: str):
            if wid == "wpn_a":
                weapon = MagicMock()
                weapon.stat1_id = "A"
                weapon.stat2_id = "B"
                weapon.stat3_id = "C"
                return weapon
            if wid == "wpn_b":
                weapon = MagicMock()
                weapon.stat1_id = "A"
                weapon.stat2_id = "B"
                weapon.stat3_id = "C"
                return weapon
            return None

        static_data.get_weapon.side_effect = _get_weapon
        return ClaimContext(entries, settings, static_data)

    def test_identical_hit_never_upgrades_other_weapon(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """同等级重复命中：不升级已有记录的下一把武器（幽灵升级场景）。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 2
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = True

        # wpn_b 已保存 (4,4,2)
        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_b",
                weapon_name="b",
                affix1_level=4,
                affix2_level=4,
                affix3_level=2,
            )
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        # 第一枚 (6,6,3)：wpn_a 首次认领
        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        first = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        assert first.accepted_weapon_id == "wpn_a"

        # 第二枚（同一基质重复命中）：不得把 wpn_b 从 (4,4,2) 升级到 (6,6,3)
        second = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        assert second.reject_reason is None
        assert ctx.best_levels["wpn_b"] == (4, 4, 2)
        assert ctx.best_levels["wpn_a"] == (6, 6, 3)
        # 仅计数（保留不落盘）：wpn_a 计数 1→2
        assert ctx.treasure_counts["wpn_a"] == 2
        assert ctx.treasure_counts["wpn_b"] == 1

    def test_identical_fills_twin_empty_slot(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """孪生武器空槽：同等级重复命中认领给组内第一把无记录的武器。"""
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 999
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = True

        ctx = ClaimContext([], default_settings, mock_static_game_data)
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        second = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert second.accepted_weapon_id == "wpn_b"
        assert ctx.best_levels == {"wpn_a": (6, 6, 3), "wpn_b": (6, 6, 3)}
        assert ctx.treasure_counts == {"wpn_a": 1, "wpn_b": 1}

    def test_identical_rescan_consumes_skip_slot(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """重扫已记录的存量基质：消耗相等跳过名额，不重复计数。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=3,
                affix2_level=3,
                affix3_level=3,
            )
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a"]

        default_essence_data.levels = [3, 3, 3]
        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        result = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert result.reject_reason is None
        assert ctx.treasure_counts["wpn_a"] == 1
        assert ctx.best_levels["wpn_a"] == (3, 3, 3)
        assert ctx.equal_skips["wpn_a"] == 0

    def test_identical_surplus_kept_within_limit(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """组内已满记录但限额未满：同等级命中判定宝藏、不落盘（仅计数）。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 2
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=3,
                affix2_level=3,
                affix3_level=3,
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_b",
                weapon_name="b",
                affix1_level=3,
                affix2_level=3,
                affix3_level=3,
            ),
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        default_essence_data.levels = [3, 3, 3]
        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        # 前两枚分别消耗 wpn_a / wpn_b 的存量跳过名额（重扫已记录基质）
        ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        # 第三枚：无存量名额、无空槽 → 保留不落盘（wpn_a 计数 1→2）
        third = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert third.reject_reason is None
        assert ctx.treasure_counts["wpn_a"] == 2
        assert ctx.treasure_counts["wpn_b"] == 1
        assert ctx.best_levels["wpn_b"] == (3, 3, 3)

    def test_identical_all_full_rejected_by_limit(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """全部武器已满额：同等级命中按限额判定为养成材料。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=3,
                affix2_level=3,
                affix3_level=3,
            )
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a"]

        default_essence_data.levels = [3, 3, 3]
        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        # 存量名额已耗尽，wpn_a 计数 1 >= limit 1 → 养成材料
        second = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert second.reject_reason == RejectReason.LIMIT
        assert second.current_count == 1

    def test_identical_no_upgrade_when_limit_off(
        self, mock_static_game_data, default_settings, default_essence_data
    ):
        """数量上限关闭：同等级重复命中同样不升级下一把武器。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = False
        default_settings.same_type_keep_best = True

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_b",
                weapon_name="b",
                affix1_level=4,
                affix2_level=4,
                affix3_level=2,
            )
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        classification = classify_essence(
            default_essence_data, default_settings, mock_static_game_data
        )
        ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        second = ctx.claim(
            classification,
            default_essence_data,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert second.reject_reason is None
        assert ctx.best_levels["wpn_b"] == (4, 4, 2)
        assert ctx.best_levels["wpn_a"] == (6, 6, 3)

    def test_limit_off_count_only_syncs_existing_best(
        self, mock_static_game_data, default_settings
    ):
        """仅计数回填：同步既有最佳等级而非更差的当前等级。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        default_settings.same_type_treasure_limit_enabled = False
        default_settings.same_type_keep_best = False

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=3,
                affix2_level=3,
                affix3_level=3,
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_b",
                weapon_name="b",
                affix1_level=2,
                affix2_level=2,
                affix3_level=2,
            ),
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        essence = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[1, 1, 1],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        classification = classify_essence(
            essence, default_settings, mock_static_game_data
        )
        result = ctx.claim(
            classification,
            essence,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        # 更差命中落回第一把武器仅计数，等级保持既有最佳 (3,3,3)
        assert result.accepted_weapon_id == "wpn_a"
        assert result.updated_levels["wpn_a"] == (3, 3, 3)
        assert ctx.treasure_counts["wpn_a"] == 2
        assert ctx.best_levels["wpn_a"] == (3, 3, 3)

    def test_init_profile_best_level_pairwise(
        self, mock_static_game_data, default_settings
    ):
        """profile 多条目最佳等级取组内真最大值（两两比较而非固定参照物）。"""
        from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

        entries = [
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=1,
                affix2_level=2,
                affix3_level=1,
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=2,
                affix2_level=1,
                affix3_level=1,
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_a",
                weapon_name="a",
                affix1_level=2,
                affix2_level=2,
                affix3_level=1,
            ),
        ]
        ctx = self._make_context_with_profile(
            entries, default_settings, mock_static_game_data
        )

        assert ctx.best_levels["wpn_a"] == (2, 2, 1)
        assert ctx.equal_skips["wpn_a"] == 1
        assert ctx.treasure_counts["wpn_a"] == 3

    def test_upgrade_cascades_freed_level_to_twin(
        self, mock_static_game_data, default_settings
    ):
        """升级释放旧等级：级联给组内下一把武器并同步计数。"""
        default_settings.same_type_treasure_limit_enabled = True
        default_settings.same_type_treasure_limit = 1
        default_settings.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        default_settings.same_type_keep_best = True

        ctx = ClaimContext([], default_settings, mock_static_game_data)
        mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_a", "wpn_b"]

        low = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[3, 3, 3],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        high = EssenceData(
            stats=["A", "B", "C"],
            stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
            levels=[4, 3, 3],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        ctx.claim(
            classify_essence(low, default_settings, mock_static_game_data),
            low,
            default_settings,
            static_game_data=mock_static_game_data,
        )
        upgraded = ctx.claim(
            classify_essence(high, default_settings, mock_static_game_data),
            high,
            default_settings,
            static_game_data=mock_static_game_data,
        )

        assert ctx.best_levels["wpn_a"] == (4, 3, 3)
        assert ctx.treasure_counts["wpn_a"] == 1
        # 释放的 (3,3,3) 级联给 wpn_b，计数同步
        assert upgraded.cascade_updated == {"wpn_b": (3, 3, 3)}
        assert ctx.best_levels["wpn_b"] == (3, 3, 3)
        assert ctx.treasure_counts["wpn_b"] == 1
