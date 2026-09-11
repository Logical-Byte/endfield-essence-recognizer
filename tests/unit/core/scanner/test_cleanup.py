"""冗余清理（实验性）：记录、名额账本、判定与回访动作的单元测试。"""

import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    AttributeLevelRecognizer,
    LockStatusLabel,
    RarityLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.recognition.template_recognizer import (
    TemplateRecognizer,
)
from endfield_essence_recognizer.core.scanner.claimer import ClaimContext
from endfield_essence_recognizer.core.scanner.classifier import classify_essence
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.scanner.engine import (
    DraggableScannerEngine,
    ScannerEngine,
    _CleanupRecord,
)
from endfield_essence_recognizer.core.scanner.models import (
    ClaimKind,
    ClaimResult,
    EssenceData,
)
from endfield_essence_recognizer.game_data.models.v2 import EssenceStatV2, StatType
from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry
from endfield_essence_recognizer.schemas.user_setting import (
    Action,
    CleanupTriggerMode,
    SameTypeGroupMode,
    UserSetting,
)
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

# ── 模拟依赖 ──


class MockImageSource:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height

    def get_client_size(self) -> tuple[int, int]:
        return self.width, self.height

    def screenshot(self, relative_region: Region | None = None) -> np.ndarray:
        if relative_region is not None:
            w = relative_region.x1 - relative_region.x0
            h = relative_region.y1 - relative_region.y0
        else:
            w, h = self.width, self.height
        return np.zeros((h, w, 3), dtype=np.uint8)


class MockWindowActions:
    def __init__(self):
        self._target_exists = True
        self._target_is_active = True
        self.click_calls: list[tuple[int, int]] = []
        self.drag_calls: list[tuple] = []

    @property
    def target_exists(self) -> bool:
        return self._target_exists

    @property
    def target_is_active(self) -> bool:
        return self._target_is_active

    def restore(self) -> bool:
        return True

    def activate(self) -> bool:
        return True

    def show(self) -> bool:
        return True

    def click(self, relative_x: int, relative_y: int) -> None:
        self.click_calls.append((relative_x, relative_y))

    def wait(self, seconds: float) -> None:
        pass

    def progressive_drag(self, *args, **kwargs) -> tuple[int, bool]:
        self.drag_calls.append(args)
        return (kwargs.get("max_drag", 0), False)


@pytest.fixture
def mock_scanner_context():
    ui_scene_recognizer = MagicMock(spec=TemplateRecognizer)
    ui_scene_recognizer.recognize_roi_fallback.return_value = (
        UISceneLabel.ESSENCE_UI,
        1.0,
    )

    attr_recognizer = MagicMock(spec=TemplateRecognizer)
    attr_recognizer.recognize_roi.return_value = ("atk", 0.9)

    attr_level_recognizer = MagicMock(spec=AttributeLevelRecognizer)
    attr_level_recognizer.recognize_level.return_value = 10

    abandon_status_recognizer = MagicMock(spec=TemplateRecognizer)
    abandon_status_recognizer.recognize_roi_fallback.return_value = (
        AbandonStatusLabel.NOT_ABANDONED,
        0.9,
    )

    lock_status_recognizer = MagicMock(spec=TemplateRecognizer)
    lock_status_recognizer.recognize_roi_fallback.return_value = (
        LockStatusLabel.NOT_LOCKED,
        0.9,
    )

    rarity_recognizer = MagicMock(spec=TemplateRecognizer)
    rarity_recognizer.recognize_roi_fallback.return_value = (RarityLabel.OTHER, 0.9)

    static_game_data = MagicMock()
    static_game_data.get_stat.return_value = MagicMock(name="TestStat")
    static_game_data.list_weapons.return_value = []
    static_game_data.get_weapon.return_value = None

    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        rarity_recognizer=rarity_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
        static_game_data=static_game_data,
    )


@pytest.fixture
def mock_profile():
    profile = MagicMock(spec=ResolutionProfile)
    profile.RESOLUTION = (1920, 1080)
    profile.ESSENCE_UI_ROI = Region(Point(38, 66), Point(143, 106))
    profile.STATS_0_ROI = Region(Point(1508, 358), Point(1700, 390))
    profile.STATS_1_ROI = Region(Point(1508, 416), Point(1700, 448))
    profile.STATS_2_ROI = Region(Point(1508, 468), Point(1700, 500))
    profile.DEPRECATE_BUTTON_ROI = Region(Point(1790, 270), Point(1823, 302))
    profile.LOCK_BUTTON_ROI = Region(Point(1825, 270), Point(1857, 302))
    profile.LOCK_BUTTON_POS = Point(1839, 286)
    profile.DEPRECATE_BUTTON_POS = Point(1807, 284)
    profile.essence_icon_x_list = [100, 200]
    profile.essence_icon_y_list = [300, 400]
    return profile


@pytest.fixture
def mock_user_setting_manager():
    manager = MagicMock(spec=UserSettingManager)
    manager.get_user_setting.return_value = UserSetting()
    return manager


def build_engine(mock_scanner_context, mock_user_setting_manager, mock_profile):
    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    engine._cleanup_active = True
    return engine


def make_data(levels: list[int | None]) -> EssenceData:
    return EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=levels,
        rarity=RarityLabel.FIVE,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )


def make_record(
    page: int,
    row: int,
    col: int,
    levels: tuple[int, int, int],
    owner: str,
    fingerprint: str = "fp",
) -> _CleanupRecord:
    return _CleanupRecord(
        page=page, row=row, col=col, levels=levels, fingerprint=fingerprint, owner=owner
    )


# ── 记录与名额账本 ──


class TestRecordCleanupClaim:
    def test_new_slot_appends_designated(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        data = make_data([4, 4, 2])
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_A"),
            data,
            page=1,
            row=0,
            col=0,
        )

        assert len(engine._cleanup_records) == 1
        record = engine._cleanup_records[0]
        assert record.levels == (4, 4, 2)
        assert record.owner == "wpn_A"
        assert record.fingerprint == engine._get_essence_hash(data)
        assert engine._cleanup_designated["wpn_A"] == [record]

    def test_record_levels_normalized_to_semantic_order(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """识别位置顺序不等于语义顺序时，记录等级必须归一化为（属性, 副属性, 技能）。"""
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        data = EssenceData(
            stats=["C", "A", "B"],
            stat_types=[StatType.SKILL, StatType.ATTRIBUTE, StatType.SECONDARY],
            levels=[3, 6, 6],
            rarity=RarityLabel.FIVE,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_A"),
            data,
            page=1,
            row=0,
            col=0,
        )
        assert engine._cleanup_records[0].levels == (6, 6, 3)

    def test_upgrade_releases_previous_holder(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_A"),
            make_data([4, 4, 2]),
            page=1,
            row=0,
            col=0,
        )
        engine._record_cleanup_claim(
            ClaimResult(
                claim_kind=ClaimKind.UPGRADE,
                owner_key="wpn_A",
                released_levels=(4, 4, 2),
            ),
            make_data([6, 5, 3]),
            page=1,
            row=1,
            col=0,
        )

        designated = engine._cleanup_designated["wpn_A"]
        assert [r.levels for r in designated] == [(6, 5, 3)]

        kept_ids = {id(r) for rs in engine._cleanup_designated.values() for r in rs}
        redundant = [r for r in engine._cleanup_records if id(r) not in kept_ids]
        assert [r.levels for r in redundant] == [(4, 4, 2)]

    def test_cascade_transfers_released_record(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_A"),
            make_data([4, 4, 2]),
            page=1,
            row=0,
            col=0,
        )
        engine._record_cleanup_claim(
            ClaimResult(
                claim_kind=ClaimKind.UPGRADE,
                owner_key="wpn_A",
                released_levels=(4, 4, 2),
                cascade_updated={"wpn_B": (4, 4, 2)},
            ),
            make_data([6, 5, 3]),
            page=1,
            row=1,
            col=0,
        )

        assert [r.levels for r in engine._cleanup_designated["wpn_A"]] == [(6, 5, 3)]
        transferred = engine._cleanup_designated["wpn_B"]
        assert [r.levels for r in transferred] == [(4, 4, 2)]
        assert transferred[0].owner == "wpn_B"

        kept_ids = {id(r) for rs in engine._cleanup_designated.values() for r in rs}
        assert all(id(r) in kept_ids for r in engine._cleanup_records)

    def test_skip_existing_and_count_only_stay_designated(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.SKIP_EXISTING, owner_key="wpn_A"),
            make_data([6, 6, 3]),
            page=1,
            row=0,
            col=0,
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.COUNT_ONLY, owner_key="wpn_A"),
            make_data([6, 6, 3]),
            page=1,
            row=1,
            col=0,
        )
        assert len(engine._cleanup_designated["wpn_A"]) == 2

    def test_none_kind_is_ignored(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NONE),
            make_data([4, 4, 2]),
            page=1,
            row=0,
            col=0,
        )
        assert engine._cleanup_records == []
        assert engine._cleanup_designated == {}

    def test_records_rollback_truncates_since_snapshot(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """过冲检测首行 pass 的记录可整体回滚，不再参与冗余判定。"""
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_A"),
            make_data([4, 4, 2]),
            page=1,
            row=0,
            col=0,
        )
        snapshot = engine._cleanup_records_snapshot()
        engine._record_cleanup_claim(
            ClaimResult(claim_kind=ClaimKind.NEW_SLOT, owner_key="wpn_B"),
            make_data([6, 6, 3]),
            page=1,
            row=1,
            col=0,
        )
        assert len(engine._cleanup_records) == 2

        engine._cleanup_records_rollback(snapshot)

        assert len(engine._cleanup_records) == 1
        assert engine._cleanup_records[0].owner == "wpn_A"
        # 被回滚的记录不再参与判定（判定只遍历 _cleanup_records）
        kept_ids = {id(r) for rs in engine._cleanup_designated.values() for r in rs}
        redundant = [r for r in engine._cleanup_records if id(r) not in kept_ids]
        assert redundant == []

    def test_init_cleanup_state_resets_navigation_state(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_flipped_pages = True
        engine._cleanup_corrected_pages = {2}
        engine._cleanup_max_page = 5

        setting = UserSetting()
        setting.redundant_cleanup_enabled = True
        engine._init_cleanup_state(setting)

        assert engine._cleanup_flipped_pages is False
        assert engine._cleanup_corrected_pages == set()
        assert engine._cleanup_max_page == 1


# ── 触发模式 ──


class TestMaybeRunCleanup:
    def test_scan_complete_trigger_skips_manual_stop(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._run_cleanup = MagicMock()
        stop_event = threading.Event()
        stop_event.set()

        setting = UserSetting()
        setting.redundant_cleanup_trigger = CleanupTriggerMode.SCAN_COMPLETE
        engine._maybe_run_cleanup(False, stop_event, setting)

        engine._run_cleanup.assert_not_called()
        assert stop_event.is_set()

    def test_always_trigger_clears_stop_event_and_runs(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._run_cleanup = MagicMock()
        stop_event = threading.Event()
        stop_event.set()

        setting = UserSetting()
        setting.redundant_cleanup_trigger = CleanupTriggerMode.ALWAYS
        engine._maybe_run_cleanup(False, stop_event, setting)

        engine._run_cleanup.assert_called_once()
        assert not stop_event.is_set()

    def test_natural_completion_runs_with_scan_complete_trigger(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._run_cleanup = MagicMock()
        stop_event = threading.Event()

        setting = UserSetting()
        setting.redundant_cleanup_trigger = CleanupTriggerMode.SCAN_COMPLETE
        engine._maybe_run_cleanup(True, stop_event, setting)

        engine._run_cleanup.assert_called_once()
        assert not stop_event.is_set()

    def test_inactive_cleanup_never_runs(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_active = False
        engine._run_cleanup = MagicMock()
        engine._maybe_run_cleanup(True, threading.Event(), UserSetting())
        engine._run_cleanup.assert_not_called()


# ── 判定与回访 ──


class TestRunCleanup:
    def test_judges_redundant_and_visits_by_page(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        kept = make_record(1, 0, 0, (6, 5, 3), "wpn_A")
        redundant_p1 = make_record(1, 1, 0, (4, 4, 2), "wpn_A")
        redundant_p3 = make_record(3, 2, 1, (3, 3, 1), "wpn_A")
        engine._cleanup_records = [kept, redundant_p1, redundant_p3]
        engine._cleanup_designated = {"wpn_A": [kept]}

        visited: list[list[_CleanupRecord]] = []
        engine._visit_cleanup_records = MagicMock(
            side_effect=lambda records, *_a, **_k: visited.append(records) or "done"
        )

        engine._run_cleanup(threading.Event(), UserSetting())

        assert visited == [[redundant_p1], [redundant_p3]]

    def test_no_redundant_logs_and_skips_navigation(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        kept = make_record(1, 0, 0, (6, 5, 3), "wpn_A")
        engine._cleanup_records = [kept]
        engine._cleanup_designated = {"wpn_A": [kept]}
        engine._visit_cleanup_records = MagicMock()

        engine._run_cleanup(threading.Event(), UserSetting())

        engine._visit_cleanup_records.assert_not_called()

    def test_page_mismatch_aborts_cleanup(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        redundant_p1 = make_record(1, 0, 0, (4, 4, 2), "wpn_A")
        redundant_p2 = make_record(2, 0, 0, (3, 3, 1), "wpn_A")
        engine._cleanup_records = [redundant_p1, redundant_p2]
        engine._cleanup_designated = {}

        engine._visit_cleanup_records = MagicMock(return_value="page_mismatch")

        engine._run_cleanup(threading.Event(), UserSetting())

        # 第一页全部不匹配 → 放弃，第二页不再回访
        assert engine._visit_cleanup_records.call_count == 1


class TestVisitCleanupRecords:
    def _recognized_fingerprint(self, engine) -> str:
        """与 mock 识别器一致的指纹：stats atk×3, levels 10×3, rarity OTHER。"""
        from endfield_essence_recognizer.core.scanner.engine import recognize_essence

        data = recognize_essence(engine._image_source, engine.ctx, engine._profile)
        return engine._get_essence_hash(data)

    def test_matching_record_deprecates_by_redundant_action(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        fingerprint = self._recognized_fingerprint(engine)
        record = make_record(1, 0, 0, (4, 4, 2), "wpn_A", fingerprint=fingerprint)

        setting = UserSetting()
        setting.redundant_action = Action.DEPRECATE

        outcome = engine._visit_cleanup_records([record], threading.Event(), setting)

        assert outcome == "done"
        # 点击基质 + 点击弃用按钮
        assert engine._window_actions.click_calls[-1] == (
            mock_profile.DEPRECATE_BUTTON_POS.x,
            mock_profile.DEPRECATE_BUTTON_POS.y,
        )

    def test_matching_record_unlocks_when_locked(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        mock_scanner_context.lock_status_recognizer.recognize_roi_fallback.return_value = (
            LockStatusLabel.LOCKED,
            0.9,
        )
        fingerprint = self._recognized_fingerprint(engine)
        record = make_record(1, 0, 0, (4, 4, 2), "wpn_A", fingerprint=fingerprint)

        setting = UserSetting()
        setting.redundant_action = Action.UNLOCK

        outcome = engine._visit_cleanup_records([record], threading.Event(), setting)

        assert outcome == "done"
        assert engine._window_actions.click_calls[-1] == (
            mock_profile.LOCK_BUTTON_POS.x,
            mock_profile.LOCK_BUTTON_POS.y,
        )

    def test_fingerprint_mismatch_page_returns_page_mismatch(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        record = make_record(1, 0, 0, (4, 4, 2), "wpn_A", fingerprint="不匹配的指纹")

        outcome = engine._visit_cleanup_records(
            [record], threading.Event(), UserSetting()
        )

        assert outcome == "page_mismatch"
        # 只有点击基质，没有动作按钮点击
        assert len(engine._window_actions.click_calls) == 1

    def test_stop_event_aborts(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = build_engine(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        stop_event = threading.Event()
        stop_event.set()
        record = make_record(1, 0, 0, (4, 4, 2), "wpn_A")

        outcome = engine._visit_cleanup_records([record], stop_event, UserSetting())

        assert outcome == "aborted"
        assert engine._window_actions.click_calls == []


# ── Draggable 导航 ──


class TestDraggableNavigation:
    def build_draggable(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        engine = DraggableScannerEngine(
            ctx=mock_scanner_context,
            image_source=MockImageSource(),
            window_actions=MockWindowActions(),
            user_setting_manager=mock_user_setting_manager,
            profile=mock_profile,
        )
        engine._cleanup_active = True
        return engine

    def test_reset_to_first_page_drag_geometry(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        mock_profile.SCROLLBAR_TOP_CHECK_POS = Point(1453, 130)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        # 翻过页且顶部亮点一直检测不到 → 走满 3 次拖动手势后放弃清理
        engine._cleanup_flipped_pages = True
        engine._check_scrollbar_at_top = MagicMock(return_value=False)

        result = engine._reset_to_first_page(threading.Event())

        assert result is False
        assert len(engine._window_actions.drag_calls) == 3
        # 拖动距离恒定 16px：起点 top+16 → 终点 top
        start_x, start_y, end_x, end_y, *_ = engine._window_actions.drag_calls[0]
        assert (start_x, start_y) == (1453, 146)
        assert (end_x, end_y) == (1453, 130)

    def test_reset_to_first_page_succeeds_when_top_confirmed(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        mock_profile.SCROLLBAR_TOP_CHECK_POS = Point(1453, 130)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_flipped_pages = True
        engine._check_scrollbar_at_top = MagicMock(return_value=True)

        assert engine._reset_to_first_page(threading.Event()) is True
        assert engine._window_actions.drag_calls == []

    def test_reset_to_first_page_skips_check_when_never_flipped(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """本轮从未翻页时物理上就在第一页，无需顶部检测。"""
        mock_profile.SCROLLBAR_TOP_CHECK_POS = Point(1453, 130)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_flipped_pages = False
        engine._check_scrollbar_at_top = MagicMock(return_value=False)

        assert engine._reset_to_first_page(threading.Event()) is True
        assert engine._window_actions.drag_calls == []
        engine._check_scrollbar_at_top.assert_not_called()

    def test_advance_to_page_flips_difference(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        mock_profile.essence_icon_y_list = [196, 351]
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._progressive_drag = MagicMock(return_value=(820, False))
        engine._align_grid_rows_after_drag = MagicMock()
        engine._check_scrollbar_at_bottom = MagicMock(return_value=False)

        setting = UserSetting()
        setting.fix_grid_row_offset_after_page_flip = True

        result = engine._advance_to_page(1, 3, threading.Event(), setting)

        assert result is True
        assert engine._progressive_drag.call_count == 2
        assert engine._align_grid_rows_after_drag.call_count == 2

    def test_advance_to_page_stops_at_bottom_when_target_is_last_scanned(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_max_page = 4
        engine._progressive_drag = MagicMock(return_value=(600, True))
        engine._align_grid_rows_after_drag = MagicMock()

        result = engine._advance_to_page(1, 4, threading.Event(), UserSetting())

        assert result is True
        # 检测到到底后不再翻页、不再对齐
        assert engine._progressive_drag.call_count == 1
        assert engine._align_grid_rows_after_drag.call_count == 0

    def test_advance_to_page_aborts_when_bottom_reached_before_target(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """提前到达底部但目标页不是最后扫描页 → 翻页序列发散，放弃清理。"""
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_max_page = 5
        engine._progressive_drag = MagicMock(return_value=(600, True))
        engine._align_grid_rows_after_drag = MagicMock()

        result = engine._advance_to_page(1, 3, threading.Event(), UserSetting())

        assert result is False
        assert engine._progressive_drag.call_count == 1
        assert engine._align_grid_rows_after_drag.call_count == 0

    def test_advance_to_page_aborts_on_post_flip_bottom_before_target(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """翻页后检测到底部但目标页不是最后扫描页 → 放弃清理。"""
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_max_page = 5
        engine._progressive_drag = MagicMock(return_value=(820, False))
        engine._align_grid_rows_after_drag = MagicMock()
        engine._check_scrollbar_at_bottom = MagicMock(return_value=True)

        result = engine._advance_to_page(1, 3, threading.Event(), UserSetting())

        assert result is False
        assert engine._progressive_drag.call_count == 1

    def test_advance_to_page_replays_overscroll_correction(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        """扫描期做过过冲校正的页，清理导航到达后重放同参数的 3/4 行校正。"""
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        mock_profile.essence_icon_y_list = [196, 351]
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_max_page = 3
        engine._cleanup_corrected_pages = {2}
        engine._progressive_drag = MagicMock(return_value=(820, False))
        engine._align_grid_rows_after_drag = MagicMock()
        engine._check_scrollbar_at_bottom = MagicMock(return_value=False)
        engine._correct_overscroll = MagicMock()

        result = engine._advance_to_page(1, 2, threading.Event(), UserSetting())

        assert result is True
        row_height = 351 - 196
        engine._correct_overscroll.assert_called_once_with(
            Point(750, 870), round(row_height * 3 / 4)
        )

    def test_advance_to_page_skips_correction_for_other_pages(
        self, mock_scanner_context, mock_user_setting_manager, mock_profile
    ):
        mock_profile.DRAG_START_POS = Point(750, 870)
        mock_profile.DRAG_END_POS = Point(750, 50)
        mock_profile.SCROLLBAR_CHECK_POS = Point(1453, 950)
        mock_profile.essence_icon_y_list = [196, 351]
        engine = self.build_draggable(
            mock_scanner_context, mock_user_setting_manager, mock_profile
        )
        engine._cleanup_max_page = 3
        engine._cleanup_corrected_pages = {2}
        engine._progressive_drag = MagicMock(return_value=(820, False))
        engine._align_grid_rows_after_drag = MagicMock()
        engine._check_scrollbar_at_bottom = MagicMock(return_value=False)
        engine._correct_overscroll = MagicMock()

        result = engine._advance_to_page(1, 3, threading.Event(), UserSetting())

        assert result is True
        engine._correct_overscroll.assert_not_called()


# ── claimer 路径标注 ──


def _make_stat(stat_id: str, stat_type: StatType) -> EssenceStatV2:
    return EssenceStatV2(stat_id=stat_id, name=stat_id, type=stat_type)


_STAT_TABLE = {
    "A": _make_stat("A", StatType.ATTRIBUTE),
    "B": _make_stat("B", StatType.SECONDARY),
    "C": _make_stat("C", StatType.SKILL),
}


def _mock_static_data() -> MagicMock:
    mock_data = MagicMock()
    mock_data.get_stat.side_effect = lambda sid: _STAT_TABLE.get(sid)
    mock_data.find_weapons_by_stats.return_value = ["wpn_001"]
    mock_data.get_weapon.return_value = None
    mock_data.get_weapon_type.return_value = None
    return mock_data


def _profile_entry(levels: tuple[int, int, int]) -> TreasureMatrixEntry:
    return TreasureMatrixEntry(
        weapon_id="wpn_001",
        weapon_name="测试武器",
        affix1_level=levels[0],
        affix2_level=levels[1],
        affix3_level=levels[2],
    )


class TestClaimKindTagging:
    def test_first_claim_is_new_slot(self):
        setting = UserSetting()
        setting.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        setting.same_type_treasure_limit = 1
        setting.same_type_keep_best = False

        context = ClaimContext([], setting)
        static_data = _mock_static_data()
        data = make_data([6, 6, 3])
        classification = classify_essence(data, setting, static_data)

        result = context.claim(
            classification, data, setting, static_game_data=static_data
        )

        assert result.claim_kind == ClaimKind.NEW_SLOT
        assert result.owner_key == "wpn_001"

    def test_existing_profile_entry_is_skip_existing(self):
        setting = UserSetting()
        setting.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        setting.same_type_treasure_limit = 1

        context = ClaimContext([_profile_entry((6, 6, 3))], setting)
        static_data = _mock_static_data()
        data = make_data([6, 6, 3])
        classification = classify_essence(data, setting, static_data)

        result = context.claim(
            classification, data, setting, static_game_data=static_data
        )

        assert result.claim_kind == ClaimKind.SKIP_EXISTING
        assert result.owner_key == "wpn_001"

    def test_upgrade_reports_released_levels(self):
        setting = UserSetting()
        setting.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        setting.same_type_treasure_limit = 1

        context = ClaimContext([_profile_entry((4, 4, 2))], setting)
        static_data = _mock_static_data()
        data = make_data([6, 5, 3])
        classification = classify_essence(data, setting, static_data)

        result = context.claim(
            classification, data, setting, static_game_data=static_data
        )

        assert result.claim_kind == ClaimKind.UPGRADE
        assert result.released_levels == (4, 4, 2)
        assert result.owner_key == "wpn_001"

    def test_identical_level_within_limit_is_count_only(self):
        setting = UserSetting()
        setting.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        setting.same_type_treasure_limit = 2

        context = ClaimContext([_profile_entry((6, 6, 3))], setting)
        static_data = _mock_static_data()
        data = make_data([6, 6, 3])
        classification = classify_essence(data, setting, static_data)

        # 第一枚：存量跳过（消耗相等跳过名额）
        first = context.claim(
            classification, data, setting, static_game_data=static_data
        )
        assert first.claim_kind == ClaimKind.SKIP_EXISTING

        # 第二枚：组内无空槽，仅计数占名额
        second = context.claim(
            classification, data, setting, static_game_data=static_data
        )
        assert second.claim_kind == ClaimKind.COUNT_ONLY
        assert second.owner_key == "wpn_001"

    def test_limit_reject_is_none(self):
        setting = UserSetting()
        setting.same_type_group_mode = SameTypeGroupMode.BY_WEAPON
        setting.same_type_treasure_limit = 1
        setting.same_type_keep_best = False

        context = ClaimContext([], setting)
        static_data = _mock_static_data()
        data = make_data([6, 6, 3])
        classification = classify_essence(data, setting, static_data)

        context.claim(classification, data, setting, static_game_data=static_data)
        second = context.claim(
            classification, data, setting, static_game_data=static_data
        )

        assert second.claim_kind == ClaimKind.NONE
        assert second.owner_key is None
