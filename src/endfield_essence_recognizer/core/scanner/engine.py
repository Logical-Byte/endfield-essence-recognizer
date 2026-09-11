import itertools
import math
import threading
from dataclasses import dataclass

import numpy as np

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
    RarityLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.scanner.action_logic import (
    ActionType,
    decide_actions,
)
from endfield_essence_recognizer.core.scanner.claimer import (
    ClaimContext,
)
from endfield_essence_recognizer.core.scanner.classifier import classify_essence
from endfield_essence_recognizer.core.scanner.context import (
    ScannerContext,
)
from endfield_essence_recognizer.core.scanner.evaluate import (
    _group_stat_key,
    _normalize_by_stat_type,
)
from endfield_essence_recognizer.core.scanner.log_builder import build_evaluation_result
from endfield_essence_recognizer.core.scanner.models import (
    ClaimKind,
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.core.window.adapter import InMemoryImageSource
from endfield_essence_recognizer.game_data.models.v2 import StatType, WeaponId
from endfield_essence_recognizer.schemas.user_setting import (
    CleanupTriggerMode,
    SameTypeGroupMode,
    UserSetting,
)
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.log import logger

#: 冗余清理回页首手势的拖动距离（像素）。不随分辨率缩放：
#: 过小的拖动可能无法被游戏识别。
_SCROLL_TOP_DRAG_PX = 16


@dataclass
class _CleanupRecord:
    """冗余清理（实验性）：单枚宝藏基质的物理记录。

    仅记录本轮扫描判定为宝藏的基质；位置使用逻辑索引（页、行、列），
    回访时结合本次会话的 ResolutionProfile 反查点击坐标。
    """

    page: int
    row: int
    col: int
    levels: tuple[int, int, int]
    fingerprint: str
    owner: str
    """最终归属武器 ID（级联可转移）。"""


def check_scene(
    image_source: ImageSource, ctx: ScannerContext, profile: ResolutionProfile
) -> bool:
    width, height = image_source.get_client_size()
    if (width, height) != profile.RESOLUTION:
        # 运行过程中窗口被调整了大小（这应该比较少见）
        logger.debug(
            "Current window size: {}, profile expects: {}",
            (width, height),
            profile.RESOLUTION,
        )
        logger.warning(
            f"当前终末地窗口分辨率为 {width}x{height}，"
            f"与预期的 {profile.RESOLUTION[0]}x{profile.RESOLUTION[1]} 不一致；"
            f"请避免在运行时调整窗口大小。"
        )
        return False

    screenshot = image_source.screenshot(profile.ESSENCE_UI_ROI)
    scene_label, _max_val = ctx.ui_scene_recognizer.recognize_roi_fallback(
        screenshot, fallback_label=UISceneLabel.UNKNOWN
    )
    if scene_label != UISceneLabel.ESSENCE_UI:
        logger.warning(
            '当前界面不是基质界面。请按 "N" 键打开贵重品库后切换到武器基质页面。'
        )
        return False
    return True


def recognize_essence(
    image_source: ImageSource,
    ctx: ScannerContext,
    profile: ResolutionProfile,
) -> EssenceData:
    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测和子区域裁剪
    mem_source = InMemoryImageSource.cache_from(image_source)
    full_screenshot = mem_source.screenshot()

    rois = [profile.STATS_0_ROI, profile.STATS_1_ROI, profile.STATS_2_ROI]

    for k, roi in enumerate(rois):
        screenshot_image = mem_source.screenshot(roi)
        attr, max_val = ctx.attr_recognizer.recognize_roi(screenshot_image)
        stats.append(attr)
        stat_display = attr
        if attr is not None:
            stat_info = ctx.static_game_data.get_stat(attr)
            if stat_info is not None:
                stat_display = f"{stat_info.name}({attr})"
        logger.debug(f"属性 {k} 识别结果: {stat_display} (分数: {max_val:.3f})")

        # 识别等级（通过检测坐标点状态）
        level_value = ctx.attr_level_recognizer.recognize_level(
            full_screenshot, k, profile
        )
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    # 识别稀有度（通过检测颜色）
    rarity_screenshot = mem_source.screenshot(profile.RARITY_ROI)
    rarity_label, score = ctx.rarity_recognizer.recognize_roi_fallback(
        rarity_screenshot, fallback_label=RarityLabel.OTHER
    )
    logger.debug(f"稀有度识别结果: {rarity_label.value} (分数: {score:.3f})")

    screenshot_image = mem_source.screenshot(profile.DEPRECATE_BUTTON_ROI)
    abandon_label, max_val = ctx.abandon_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=AbandonStatusLabel.MAYBE_ABANDONED,
    )
    logger.debug(f"弃用按钮识别结果: {abandon_label.value} (分数: {max_val:.3f})")

    screenshot_image = mem_source.screenshot(profile.LOCK_BUTTON_ROI)
    locked_label, max_val = ctx.lock_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=LockStatusLabel.MAYBE_LOCKED,
    )
    logger.debug(f"锁定按钮识别结果: {locked_label.value} (分数: {max_val:.3f})")

    # 根据识别出的 stat_id 查询每个位置的语义类型（ATTRIBUTE / SECONDARY / SKILL）
    stat_types: list[StatType | None] = []
    for stat in stats:
        if stat is None:
            stat_types.append(None)
        else:
            stat_info = ctx.static_game_data.get_stat(stat)
            if stat_info is not None:
                stat_types.append(stat_info.type)
            else:
                stat_types.append(None)
                logger.warning(f"无法在静态数据中找到基质 ID: {stat} 的类型")

    stats_name_parts = []
    for i, stat in enumerate(stats):
        if stat is None:
            stats_name_parts.append("无")
        else:
            gem = ctx.static_game_data.get_stat(stat)
            if gem is not None:
                stat_name = gem.name
            else:
                # this should not happen
                logger.warning(f"无法在静态数据中找到基质 ID: {stat} 的名称")
                stat_name = stat
            if i < len(levels) and levels[i] is not None:
                stats_name_parts.append(f"{stat_name}+{levels[i]}")
            else:
                stats_name_parts.append(stat_name)
    stats_name = "、".join(stats_name_parts)

    rarity_text = {
        RarityLabel.FIVE: "<yellow>无瑕</>",
        RarityLabel.FOUR: "<magenta>高纯</>",
        RarityLabel.OTHER: "其他",
    }.get(rarity_label, "未知")

    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats_name}</>, 稀有度: {rarity_text}, <magenta>{abandon_label.value}</>, <magenta>{locked_label.value}</>"
    )

    return EssenceData(
        stats, stat_types, levels, rarity_label, abandon_label, locked_label
    )


def recognize_once(
    image_source: ImageSource,
    ctx: ScannerContext,
    user_setting: UserSetting,
    profile: ResolutionProfile,
) -> None:
    mem_source = InMemoryImageSource.cache_from(image_source)

    check_scene_result = check_scene(mem_source, ctx, profile)
    if not check_scene_result:
        return

    data = recognize_essence(
        mem_source,
        ctx,
        profile,
    )

    if (
        data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
        or data.lock_label == LockStatusLabel.MAYBE_LOCKED
    ):
        return

    # 单次识别：仅分类和日志，不认领
    classification = classify_essence(data, user_setting, ctx.static_game_data)
    from endfield_essence_recognizer.core.scanner.claimer import ClaimResult

    evaluation = build_evaluation_result(
        classification,
        ClaimResult(),
        ctx.static_game_data,
        user_setting,
    )
    # all logs use success for simplicity
    logger.opt(colors=True).success(evaluation.log_message)


class OneTimeRecognitionEngine:
    """
    单次基质识别引擎。

    此引擎执行一次性识别流程，包括窗口激活、场景检查、基质信息识别与评估；不会执行点击操作。
    """

    def __init__(
        self,
        ctx: ScannerContext,
        image_source: ImageSource,
        window_actions: WindowActions,
        user_setting_manager: UserSettingManager,
        profile: ResolutionProfile,
    ) -> None:
        self.ctx: ScannerContext = ctx
        self._image_source = image_source
        self._window_actions = window_actions
        self._user_setting_manager: UserSettingManager = user_setting_manager
        self._profile: ResolutionProfile = profile

    def execute(self, stop_event: threading.Event) -> None:
        """
        执行单次识别流程。
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止单次识别。")
            return

        if not self._window_actions.target_is_active:
            logger.debug("终末地窗口不在前台，尝试切换到前台以进行识别基质操作。")
            if self._window_actions.activate():
                self._window_actions.wait(0.3)
            if self._window_actions.show():
                # make sure the window is visible
                self._window_actions.wait(0.3)

        if stop_event.is_set():
            return

        user_setting = self._user_setting_manager.get_user_setting()
        recognize_once(
            self._image_source,
            self.ctx,
            user_setting,
            self._profile,
        )


class ScannerEngine:
    """
    基质图标扫描器引擎。

    此引擎负责自动遍历游戏界面中的 45 个基质图标位置，
    对每个位置执行"点击 -> 截图 -> 识别"的流程。
    """

    def __init__(
        self,
        ctx: ScannerContext,
        image_source: ImageSource,
        window_actions: WindowActions,
        user_setting_manager: UserSettingManager,
        profile: ResolutionProfile,
    ) -> None:
        self.ctx: ScannerContext = ctx
        self._image_source = image_source
        self._window_actions = window_actions
        self._user_setting_manager: UserSettingManager = user_setting_manager
        self._profile: ResolutionProfile = profile

        # 以下字段是 ScannerEngine 维护的运行时状态
        self._weapon_essence_counts: dict[WeaponId, int] = {}
        self._weapon_essence_levels: dict[WeaponId, tuple[int, int, int]] = {}
        self._total_essence_count: int = 0
        # 跟踪每个属性组合已跳过的同等级基质次数
        self._skip_exact_level_counts: dict[tuple, int] = {}

        # 冗余清理（实验性）运行时状态
        self._cleanup_active = False
        self._cleanup_records: list[_CleanupRecord] = []
        self._cleanup_designated: dict[str, list[_CleanupRecord]] = {}
        self._cleanup_page_index = 1
        self._cleanup_flipped_pages = False
        self._cleanup_corrected_pages: set[int] = set()
        self._cleanup_max_page = 1

        from endfield_essence_recognizer.utils.log import str_properties_and_attrs

        logger.opt(lazy=True).debug(
            "Scanner profile configuration: {}",
            lambda: str_properties_and_attrs(profile),
        )

    def execute(self, stop_event: threading.Event) -> None:
        """
        Run the 9*5 grid scanning process with start/end logging.
        """
        logger.debug("ScannerEngine started execution.")
        self._execute_grid_scan(stop_event)
        logger.debug("ScannerEngine finished execution.")

    def get_weapon_essence_counts(self) -> dict[WeaponId, int]:
        """
        Get the weapon essence counts from the last scan.

        Returns:
            A dictionary mapping weapon IDs to essence counts.
        """
        return self._get_display_essence_counts()

    def get_weapon_essence_data(self):
        """
        获取完整的武器基质数据（包括等级）。

        Returns:
            WeaponEssenceData 对象，包含计数和等级信息。
        """
        from endfield_essence_recognizer.schemas.scanner import WeaponEssenceData

        return WeaponEssenceData(
            counts=self._get_display_essence_counts(),
            levels=self._weapon_essence_levels.copy(),
        )

    def _get_display_essence_counts(self) -> dict[WeaponId, int]:
        """按属性组合聚合的武器基质数量（同组显示组总数，孪生武器共享）。

        组内每把武器显示该属性组合扫描到的匹配基质总枚数（含被非降级/留大弃小
        拒绝的）；无组计数时回退为逐武器认领计数。纯自定义匹配不产生组计数。
        """
        if not hasattr(self, "_claim_context") or self._claim_context is None:
            return self._weapon_essence_counts.copy()
        group_counts = self._claim_context.get_group_scanned_counts()
        if not group_counts:
            return self._weapon_essence_counts.copy()
        result: dict[WeaponId, int] = {}
        for stat_key, count in group_counts.items():
            for weapon_id in self.ctx.static_game_data.find_weapons_by_stats(*stat_key):
                result[weapon_id] = count
        return result

    # ── 冗余清理（实验性）──

    def _init_cleanup_state(self, user_setting: UserSetting) -> None:
        """按用户设置初始化本轮扫描的冗余清理状态（无副作用）。"""
        self._cleanup_records = []
        self._cleanup_designated = {}
        self._cleanup_page_index = 1
        self._cleanup_flipped_pages = False
        self._cleanup_corrected_pages = set()
        self._cleanup_max_page = 1
        self._cleanup_active = (
            user_setting.redundant_cleanup_enabled
            and user_setting.same_type_treasure_limit_enabled
            and user_setting.same_type_group_mode == SameTypeGroupMode.BY_WEAPON
        )
        if user_setting.redundant_cleanup_enabled and not self._cleanup_active:
            logger.warning(
                "冗余清理已开启，但当前配置暂不支持（需启用数量上限且按武器划分），本次跳过。"
            )

    def _get_essence_hash(self, data: EssenceData) -> str:
        """
        生成基质指纹用于去重检测。

        使用稀有度、属性类型和属性等级作为指纹。
        """
        stats_str = "_".join(str(s) if s is not None else "?" for s in data.stats)
        levels_str = "_".join(str(lv) if lv is not None else "?" for lv in data.levels)
        return f"{data.rarity.value}_{stats_str}_{levels_str}"

    def _record_cleanup_claim(
        self,
        claim_result,
        data: EssenceData,
        page: int,
        row: int,
        col: int,
    ) -> None:
        """按认领路径把一枚宝藏基质记入冗余清理的名额账本。

        账本语义与 ClaimContext 的名额状态机一致：
        - 新增名额 / 仅计数 / 存量跳过 → 追加为当前持有者；
        - 升级替换 → 释放旧最优持有者，级联则把释放记录转移归属。
        """
        kind = claim_result.claim_kind
        if kind not in (
            ClaimKind.NEW_SLOT,
            ClaimKind.UPGRADE,
            ClaimKind.SKIP_EXISTING,
            ClaimKind.COUNT_ONLY,
        ):
            return
        owner = claim_result.owner_key
        if not isinstance(owner, str) or not owner:
            return

        # 记录语义顺序（属性、副属性、技能）的等级，与 claimer 的
        # released_levels / best_levels 对齐；识别位置顺序不保证等于语义顺序
        _stat_key, _ordered_types, current_levels = _normalize_by_stat_type(
            data.stats, data.stat_types, data.levels
        )
        record = _CleanupRecord(
            page=page,
            row=row,
            col=col,
            levels=current_levels,
            fingerprint=self._get_essence_hash(data),
            owner=owner,
        )
        self._cleanup_records.append(record)
        self._cleanup_designated.setdefault(owner, []).append(record)

        if kind == ClaimKind.UPGRADE:
            released = self._release_cleanup_holder(owner, claim_result.released_levels)
            if released is not None and claim_result.cascade_updated:
                # 级联：释放的旧等级转移给目标武器（_cascade_freed 每次至多一个目标）
                for target_weapon in claim_result.cascade_updated:
                    released.owner = target_weapon
                    self._cleanup_designated.setdefault(target_weapon, []).append(
                        released
                    )
                    break

    def _release_cleanup_holder(
        self, owner: str, released_levels: tuple[int, int, int] | None
    ) -> _CleanupRecord | None:
        """释放 owner 当前最优持有者（最近追加的同等级记录）；找不到则返回 None。"""
        if released_levels is None:
            return None
        records = self._cleanup_designated.get(owner)
        if not records:
            return None
        for index in range(len(records) - 1, -1, -1):
            if records[index].levels == released_levels:
                return records.pop(index)
        return None

    def _cleanup_records_snapshot(self) -> int:
        """返回当前账本记录数，供翻页过冲检测首行 pass 的回滚使用。"""
        return len(self._cleanup_records)

    def _cleanup_records_rollback(self, snapshot: int) -> None:
        """回滚自快照以来新增的账本记录。

        翻页过冲检测时，首行扫到的是上一页的重复基质，其位置记录会随
        3/4 行校正失效；回滚后这些基质仍由上一页的正确位置记录覆盖。
        designated 中残留的引用无副作用：判定只遍历 _cleanup_records。
        """
        del self._cleanup_records[snapshot:]

    def _maybe_run_cleanup(
        self,
        scan_completed_naturally: bool,
        stop_event: threading.Event,
        user_setting: UserSetting,
    ) -> None:
        """按触发模式决定是否执行冗余清理。

        手动停止触发的清理会先清除停止事件（清理过程中用户可再次按停止取消）。
        """
        if not self._cleanup_active:
            return
        if not scan_completed_naturally and (
            user_setting.redundant_cleanup_trigger != CleanupTriggerMode.ALWAYS
        ):
            return
        if not scan_completed_naturally:
            stop_event.clear()
        try:
            self._run_cleanup(stop_event, user_setting)
        except Exception:
            logger.exception("冗余清理执行失败，已跳过。")

    def _run_cleanup(
        self, stop_event: threading.Event, user_setting: UserSetting
    ) -> None:
        """执行冗余清理：判定冗余 → 回第一页 → 逐页回访 → 按规则操作。"""
        kept_ids = {
            id(record)
            for records in self._cleanup_designated.values()
            for record in records
        }
        redundant = [
            record for record in self._cleanup_records if id(record) not in kept_ids
        ]
        if not redundant:
            logger.info("冗余清理：本轮扫描没有冗余基质。")
            return

        logger.info(f"冗余清理：发现 {len(redundant)} 枚冗余基质，开始清理。")
        self._cleanup_max_page = max((record.page for record in redundant), default=1)
        if not self._reset_to_first_page(stop_event):
            # 放弃原因已由 _reset_to_first_page 记录；停止事件则补一条中断日志
            if stop_event.is_set():
                logger.info("冗余清理被中断。")
            return
        current_page = 1

        by_page: dict[int, list[_CleanupRecord]] = {}
        for record in redundant:
            by_page.setdefault(record.page, []).append(record)

        for page in sorted(by_page):
            if not self._window_actions.target_is_active:
                logger.warning("终末地窗口不在前台，中止冗余清理。")
                return
            if stop_event.is_set():
                logger.info("冗余清理被中断。")
                return
            if not self._advance_to_page(current_page, page, stop_event, user_setting):
                logger.warning("冗余清理：翻页失败，放弃本次清理。")
                return
            current_page = page
            outcome = self._visit_cleanup_records(
                by_page[page], stop_event, user_setting
            )
            if outcome == "page_mismatch":
                logger.warning("冗余清理：整页指纹均不匹配，放弃本次清理。")
                return
            if outcome == "aborted":
                return
        logger.info("冗余清理：清理完成。")

    def _visit_cleanup_records(
        self,
        page_records: list[_CleanupRecord],
        stop_event: threading.Event,
        user_setting: UserSetting,
    ) -> str:
        """回访一页内的冗余基质并按「对于冗余基质」规则操作。

        Returns:
            "done" 至少一枚指纹匹配 / "page_mismatch" 全部不匹配 /
            "aborted" 窗口失焦或用户停止。
        """
        matched_any = False
        for record in page_records:
            if not self._window_actions.target_is_active:
                logger.warning("终末地窗口不在前台，中止冗余清理。")
                return "aborted"
            if stop_event.is_set():
                logger.info("冗余清理被中断。")
                return "aborted"

            position = f"第{record.page}页第{record.row + 1}行第{record.col + 1}列"
            self._window_actions.click(
                self._profile.essence_icon_x_list[record.col],
                self._profile.essence_icon_y_list[record.row],
            )
            self._window_actions.wait(0.3)

            data = recognize_essence(self._image_source, self.ctx, self._profile)
            if (
                data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or data.lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                logger.warning(f"[冗余清理] {position} 识别不确定，跳过。")
                continue
            if self._get_essence_hash(data) != record.fingerprint:
                logger.warning(f"[冗余清理] {position} 指纹不匹配，跳过。")
                continue

            matched_any = True
            levels_text = "/".join(str(level) for level in record.levels)
            evaluation = EvaluationResult(
                quality=EssenceQuality.TRASH,
                log_message="",
            )
            actions = decide_actions(
                data,
                evaluation,
                user_setting,
                target_action=user_setting.redundant_action,
            )
            if not actions:
                logger.info(
                    f"[冗余清理] {position} 等级 {levels_text} 已符合目标状态，无需操作。"
                )
                continue

            for action in actions:
                if action.type == ActionType.CLICK_LOCK:
                    pos = self._profile.LOCK_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                elif action.type == ActionType.CLICK_ABANDON:
                    pos = self._profile.DEPRECATE_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                self._window_actions.wait(0.3)
            logger.opt(colors=True).success(
                f"[冗余清理] {position} 基质等级 <magenta>{levels_text}</> "
                "已按「对于冗余基质」规则处理。"
            )
        return "done" if matched_any else "page_mismatch"

    def _reset_to_first_page(self, stop_event: threading.Event) -> bool:
        """回到第一页。基类无翻页：当前页即第一页。"""
        return True

    def _advance_to_page(
        self,
        current_page: int,
        target_page: int,
        stop_event: threading.Event,
        user_setting: UserSetting,
    ) -> bool:
        """从当前页前进到目标页。基类无翻页：直接成功。"""
        return True

    def _sort_weapons_by_priority(self, weapon_ids: set[str]) -> list[str]:
        """按优先级排序武器ID（高优先级在前）。

        排序规则：
        1. 用户设置的 priority（正数）优先于默认值
        2. 默认值按稀有度降序排列
        3. 同优先级按武器 ID 升序，保证分配顺序确定可复现
        """
        priority_map: dict[str, int] = {}
        try:
            from endfield_essence_recognizer.api.routes.profiles import (
                get_profile_manager,
            )

            profile_manager = get_profile_manager()
            profile = profile_manager.get_active_profile()
            for weapon_id, priority in profile.weapon_priorities.items():
                if weapon_id in weapon_ids:
                    priority_map[weapon_id] = priority or 0
            for entry in profile.treasure_matrix:
                if entry.weapon_id in weapon_ids:
                    priority_map.setdefault(entry.weapon_id, entry.priority or 0)
        except Exception as exc:
            logger.debug("未能加载武器优先级配置，使用默认排序: {}", exc)

        def get_priority(weapon_id: str) -> int:
            user_priority = priority_map.get(weapon_id, 0)
            if user_priority > 0:
                return user_priority
            weapon = self.ctx.static_game_data.get_weapon(weapon_id)
            return weapon.rarity if weapon else 0

        # 同优先级按武器 ID 升序（元组第二键），避免集合迭代顺序导致的不确定性
        return sorted(weapon_ids, key=lambda wid: (-get_priority(wid), wid))

    def _resolve_weapon_id(self, weapon_id_or_name: str) -> str:
        """将武器名称归一化为武器 ID；已是合法 ID 则原样返回。"""
        if self.ctx.static_game_data.get_weapon(weapon_id_or_name) is not None:
            return weapon_id_or_name
        # 按名称查找
        for w in self.ctx.static_game_data.list_weapons():
            if w.name == weapon_id_or_name:
                return w.weapon_id
        return weapon_id_or_name

    def _get_stat_tuple(self, weapon_ids: set[str]) -> tuple:
        """获取一组武器的属性组合作为 hashable key。"""
        return _group_stat_key(weapon_ids, self.ctx.static_game_data)

    def _weapon_display(self, weapon_id: str) -> str:
        """返回 "武器名称(武器ID)" 格式，便于日志排查。"""
        weapon = self.ctx.static_game_data.get_weapon(weapon_id)
        if weapon:
            return f"{weapon.name}({weapon_id})"
        return weapon_id

    def _init_weapon_levels_from_profile(self) -> None:
        """从 profile 的宝藏基质配置中初始化已有武器等级。"""
        try:
            from endfield_essence_recognizer.api.routes.profiles import (
                get_profile_manager,
            )

            profile = get_profile_manager().get_active_profile()
            for entry in profile.treasure_matrix:
                weapon_id = self._resolve_weapon_id(entry.weapon_id)
                self._weapon_essence_levels[weapon_id] = (
                    entry.affix1_level,
                    entry.affix2_level,
                    entry.affix3_level,
                )
        except Exception as exc:
            logger.debug("未能从账号配置初始化武器等级: {}", exc)

    def _assign_essence_to_weapon(
        self,
        matched_weapon_ids: set[str],
        levels: list[int | None],
    ) -> None:
        """将一个基质按优先级分配给单把武器。

        规则：
        1. 只分配给一把武器（优先级最高的可接受武器）
        2. 非降级原则：基质各维度等级必须 >= 武器当前等级才可更新
        3. 同属性组中已有 N 把武器的当前等级与基质等级完全相同时，
           前 N 次跳过（归属不确定），后续可分配给下一把武器
        """
        if not matched_weapon_ids:
            return

        sorted_weapons = self._sort_weapons_by_priority(matched_weapon_ids)

        current_levels = (
            levels[0] or 1,
            levels[1] or 1,
            levels[2] or 1,
        )

        # 统计组内已有多少把武器的等级与当前基质完全相同
        exact_match_count = sum(
            1
            for wid in sorted_weapons
            if self._weapon_essence_levels.get(wid) == current_levels
        )

        # 同等级跳过：已有 N 把武器拥有相同等级，前 N 次跳过
        if exact_match_count > 0:
            stat_key = self._get_stat_tuple(matched_weapon_ids)
            skip_key = (stat_key, current_levels)
            skip_count = self._skip_exact_level_counts.get(skip_key, 0)
            if skip_count < exact_match_count:
                self._skip_exact_level_counts[skip_key] = skip_count + 1
                logger.debug(
                    f"基质等级{current_levels}与{exact_match_count}把同属性武器相同，"
                    f"已跳过{skip_count + 1}/{exact_match_count}次（归属不确定）"
                )
                return
            # 已跳过足够次数，后续可分配

        # 非降级原则检查：所有维度 >= 武器当前等级
        def can_upgrade(weapon_id: str) -> bool:
            existing = self._weapon_essence_levels.get(weapon_id)
            if existing is None:
                return True
            return (
                current_levels[0] >= existing[0]
                and current_levels[1] >= existing[1]
                and current_levels[2] >= existing[2]
            )

        # 找到第一个可接受该基质的高优先级武器
        blocked_by_downgrade = False
        for weapon_id in sorted_weapons:
            existing_levels = self._weapon_essence_levels.get(weapon_id)

            # 已拥有相同等级的武器跳过（已在上面的 exact_match_count 中处理）
            if existing_levels == current_levels:
                continue

            # 非降级检查
            if not can_upgrade(weapon_id):
                blocked_by_downgrade = True
                logger.debug(
                    f"武器 {self._weapon_display(weapon_id)} 当前等级 {existing_levels}，"
                    f"基质等级 {current_levels}，不满足非降级原则，跳过"
                )
                continue

            # 分配基质
            self._weapon_essence_counts[weapon_id] = (
                self._weapon_essence_counts.get(weapon_id, 0) + 1
            )

            # 更新等级
            if existing_levels:
                self._weapon_essence_levels[weapon_id] = (
                    max(existing_levels[0], current_levels[0]),
                    max(existing_levels[1], current_levels[1]),
                    max(existing_levels[2], current_levels[2]),
                )
            else:
                self._weapon_essence_levels[weapon_id] = current_levels

            return  # 只分配给一把武器

        if blocked_by_downgrade:
            logger.debug(
                f"基质等级 {current_levels} 对所有可选武器均不满足非降级原则，已忽略"
            )
            return

        # 没有可分配的武器，分配给最高优先级的（仅计数）
        if sorted_weapons:
            weapon_id = sorted_weapons[0]
            self._weapon_essence_counts[weapon_id] = (
                self._weapon_essence_counts.get(weapon_id, 0) + 1
            )

    def _execute_grid_scan(self, stop_event: threading.Event) -> None:
        """
        Actual execution logic for a 9*5 grid pass.
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止基质扫描。")
            return

        if self._window_actions.restore():
            self._window_actions.wait(0.5)

        if self._window_actions.activate():
            self._window_actions.wait(0.5)

        if self._window_actions.show():
            # make the window visible in the beginning
            self._window_actions.wait(0.5)

        logger.debug("Made the window visible and active.")

        check_scene_result = check_scene(self._image_source, self.ctx, self._profile)
        if not check_scene_result:
            return

        # 获取当前用户设置的快照，用于接下来的判断
        user_setting = self._user_setting_manager.get_user_setting()

        # 重置武器基质数量统计
        self._weapon_essence_counts = {}
        self._weapon_essence_levels = {}
        self._total_essence_count = 0
        self._skip_exact_level_counts = {}

        # 初始化冗余清理（实验性）状态
        self._init_cleanup_state(user_setting)

        # 从 profile 初始化已有武器等级，用于同等级跳过判断
        self._init_weapon_levels_from_profile()

        # 创建 ClaimContext（从 profile 初始化最佳等级/计数/相等跳过名额）
        try:
            from endfield_essence_recognizer.api.routes.profiles import (
                get_profile_manager,
            )

            profile = get_profile_manager().get_active_profile()
            self._claim_context = ClaimContext(
                profile.treasure_matrix, user_setting, self.ctx.static_game_data
            )
        except Exception as exc:
            logger.debug("未能创建 ClaimContext: {}", exc)
            self._claim_context = ClaimContext(
                [], user_setting, self.ctx.static_game_data
            )

        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        # 是否自然完成（未被打断）；冗余清理按此区分触发模式
        scan_completed_naturally = False

        for (i, relative_y), (j, relative_x) in itertools.product(
            enumerate(icon_y_list), enumerate(icon_x_list)
        ):
            if not self._window_actions.target_is_active:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                break

            if stop_event.is_set():
                logger.info("基质扫描被中断。")
                break

            logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

            # 点击基质图标位置
            self._window_actions.click(relative_x, relative_y)

            # 等待短暂时间以确保界面更新
            self._window_actions.wait(0.3)

            # 识别基质信息
            data = recognize_essence(
                self._image_source,
                self.ctx,
                self._profile,
            )

            if (
                data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or data.lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                # early continue on uncertain recognition
                continue

            # 预先获取所有武器的优先级排序，传递给 claim 函数
            all_weapon_ids = set(self._weapon_essence_counts.keys()) | set(
                self._weapon_essence_levels.keys()
            )
            for w in self.ctx.static_game_data.list_weapons():
                all_weapon_ids.add(w.weapon_id)
            weapon_priority_order = self._sort_weapons_by_priority(all_weapon_ids)

            # Layer 1: 分类
            classification = classify_essence(
                data, user_setting, self.ctx.static_game_data
            )

            # Layer 2: 认领
            claim_result = self._claim_context.claim(
                classification,
                data,
                user_setting,
                weapon_essence_levels=self._weapon_essence_levels,
                weapon_priority_order=weapon_priority_order,
                static_game_data=self.ctx.static_game_data,
            )

            # Layer 3: 组装 log_message
            evaluation = build_evaluation_result(
                classification,
                claim_result,
                self.ctx.static_game_data,
                user_setting,
                weapon_priority_order=weapon_priority_order,
            )

            # 统计基质总数（跳过 SKIP 的基质）
            if evaluation.quality != EssenceQuality.SKIP:
                self._total_essence_count += 1

            # 冗余清理（实验性）：记录本轮判为宝藏的基质
            if self._cleanup_active and evaluation.quality == EssenceQuality.TREASURE:
                self._record_cleanup_claim(claim_result, data, page=1, row=i, col=j)

            # 同步认领结果到引擎
            for weapon_id, levels in claim_result.updated_levels.items():
                self._weapon_essence_levels[weapon_id] = levels
                count = self._claim_context.treasure_counts.get(weapon_id, 0)
                if count > 0:
                    self._weapon_essence_counts[weapon_id] = count

            for weapon_id, levels in claim_result.cascade_updated.items():
                self._weapon_essence_levels[weapon_id] = levels
                count = self._claim_context.treasure_counts.get(weapon_id, 0)
                if count > 0:
                    self._weapon_essence_counts[weapon_id] = count

            # Log the result
            if (
                evaluation.quality == EssenceQuality.TRASH
                and evaluation.matched_weapons
            ):
                logger.opt(colors=True).warning(evaluation.log_message)
            else:
                logger.opt(colors=True).success(evaluation.log_message)

            if evaluation.stop_scan:
                logger.info("已根据设置结束本次基质扫描。")
                stop_event.set()
                break

            # Decide actions
            actions = decide_actions(data, evaluation, user_setting)

            # Execute actions
            for action in actions:
                if action.type == ActionType.CLICK_LOCK:
                    pos = self._profile.LOCK_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                elif action.type == ActionType.CLICK_ABANDON:
                    pos = self._profile.DEPRECATE_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)

                self._window_actions.wait(0.3)
                logger.opt(colors=True).success(
                    f"<LIGHT-YELLOW><bold>{action.log_message}</></>"
                )

        else:
            # 扫描完成
            logger.info("基质扫描完成")
            scan_completed_naturally = True

        # 冗余清理（实验性）：按触发模式执行
        self._maybe_run_cleanup(scan_completed_naturally, stop_event, user_setting)

        # 输出武器基质数量统计
        logger.info(f"共扫描了 {self._total_essence_count} 个基质。")
        display_counts = self._get_display_essence_counts()
        if display_counts:
            # 按 稀有度降序 武器ID 排序
            def sort_key(item: tuple[WeaponId, int]) -> tuple[int, WeaponId]:
                weapon_id, _ = item
                weapon = self.ctx.static_game_data.get_weapon(weapon_id)
                # 负数使稀有度按降序排序
                rarity = -weapon.rarity if weapon else 0
                return (rarity, weapon_id)

            sorted_counts = sorted(display_counts.items(), key=sort_key)

            logger.info("武器基质数量统计：")
            for weapon_id, count in sorted_counts:
                weapon = self.ctx.static_game_data.get_weapon(weapon_id)
                if weapon:
                    weapon_type = self.ctx.static_game_data.get_weapon_type(
                        weapon.weapon_type
                    )
                    type_name = weapon_type.name if weapon_type else "未知类型"
                    rarity_color = self.ctx.static_game_data.get_rarity_color(
                        weapon.rarity
                    )
                    logger.opt(colors=True).info(
                        f"  <fg {rarity_color}><bold>{weapon.name}（{weapon.rarity}★ {type_name}）</></>: {count} 个基质"
                    )
                else:
                    logger.opt(colors=True).info(
                        f"  <bold>{weapon_id}</>: {count} 个基质"
                    )
        elif self._total_essence_count > 0:
            # 扫描了基质但没有匹配到任何武器
            logger.info("没有匹配到任何非垃圾武器。")


class DraggableScannerEngine(ScannerEngine):
    """
    支持拖拽翻页的基质扫描器引擎。

    继承自 ScannerEngine，添加了自动翻页功能：
    - 通过拖拽操作实现翻页
    - 检测滚动条位置判断是否到达底部
    - 支持翻页前后去重（避免重复扫描）
    """

    def _execute_grid_scan(self, stop_event: threading.Event) -> None:
        """
        执行带拖拽翻页的网格扫描。
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止基质扫描。")
            return

        if self._window_actions.restore():
            self._window_actions.wait(0.5)

        if self._window_actions.activate():
            self._window_actions.wait(0.5)

        if self._window_actions.show():
            self._window_actions.wait(0.5)

        logger.debug("Made the window visible and active.")

        check_scene_result = check_scene(self._image_source, self.ctx, self._profile)
        if not check_scene_result:
            return

        # 获取当前用户设置的快照
        user_setting = self._user_setting_manager.get_user_setting()

        # 重置武器基质数量统计
        self._weapon_essence_counts = {}
        self._weapon_essence_levels = {}
        self._total_essence_count = 0
        self._skip_exact_level_counts = {}
        # 重置已扫描基质指纹集合（用于翻页去重检测）
        self._scanned_essence_hashes: set[str] = set()

        # 初始化冗余清理（实验性）状态
        self._init_cleanup_state(user_setting)

        # 从 profile 初始化已有武器等级，用于同等级跳过判断
        self._init_weapon_levels_from_profile()

        # 创建 ClaimContext（从 profile 初始化最佳等级/计数/相等跳过名额）
        try:
            from endfield_essence_recognizer.api.routes.profiles import (
                get_profile_manager,
            )

            profile = get_profile_manager().get_active_profile()
            self._claim_context = ClaimContext(
                profile.treasure_matrix, user_setting, self.ctx.static_game_data
            )
        except Exception as exc:
            logger.debug("未能创建 ClaimContext: {}", exc)
            self._claim_context = ClaimContext(
                [], user_setting, self.ctx.static_game_data
            )

        # 检查是否启用自动翻页
        auto_page_flip = user_setting.auto_page_flip
        if not auto_page_flip:
            logger.info("自动翻页已关闭，将只扫描当前页。")
            # 调用父类的单页扫描逻辑
            super()._execute_grid_scan(stop_event)
            return

        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        # 获取拖动配置
        drag_start = self._profile.DRAG_START_POS
        drag_end = self._profile.DRAG_END_POS

        # 获取滚动条检测配置
        scrollbar_pos = self._profile.SCROLLBAR_CHECK_POS

        page_count = 0
        is_last_page = False
        max_pages = 100  # 最大页数限制，防止无限循环

        # 是否自然完成（扫到最后一页）；冗余清理按此区分触发模式
        scan_completed_naturally = False

        # 初始化渐进拖动相关变量
        progressive_drag_distance = 0
        max_drag_distance = (
            int((drag_end.x - drag_start.x) ** 2 + (drag_end.y - drag_start.y) ** 2)
            ** 0.5
        )
        total_rows = len(icon_y_list)

        while not stop_event.is_set() and page_count < max_pages:
            page_count += 1
            logger.info(f"开始扫描第 {page_count} 页基质...")
            self._cleanup_page_index = page_count
            if page_count > 1:
                self._cleanup_flipped_pages = True

            if is_last_page and page_count > 1:
                # 最后一页：根据渐进滚动距离计算需要跳过的行数
                row_height = (
                    icon_y_list[1] - icon_y_list[0] if len(icon_y_list) > 1 else 0
                )
                skip_rows = self._calculate_skip_rows(
                    progressive_drag_distance, row_height, total_rows
                )
                start_row = min(skip_rows, total_rows - 1)
                logger.info(
                    f"最后一页：滚动距离 {progressive_drag_distance}px（完整页 {max_drag_distance:.0f}px），跳过前 {start_row} 行已扫描基质"
                )
                self._scan_current_page(
                    stop_event,
                    user_setting,
                    icon_x_list,
                    icon_y_list,
                    start_row_index=start_row,
                )
            elif page_count > 1:
                # 非首页：先扫描第一行（含操作），检测是否全部重复。
                # 冗余清理：过冲检测首行先不入账——若确认过冲并执行 3/4 行
                # 校正，该 pass 的位置记录作废，回滚账本；该页校正后的网格
                # 偏移记入 _cleanup_corrected_pages，清理导航时重放校正。
                cleanup_snapshot = self._cleanup_records_snapshot()
                all_dup = self._scan_single_row(
                    0, stop_event, user_setting, icon_x_list, icon_y_list
                )
                if all_dup and user_setting.fix_page_flip_overscroll:
                    self._cleanup_records_rollback(cleanup_snapshot)
                    self._cleanup_corrected_pages.add(page_count)
                    row_height = (
                        icon_y_list[1] - icon_y_list[0] if len(icon_y_list) > 1 else 0
                    )
                    adjust_distance = round(row_height * 3 / 4)
                    self._correct_overscroll(drag_start, adjust_distance)
                    logger.info(
                        "检测到第一行为重复基质，已向上微调 3/4 行，重新扫描第一行"
                    )
                    self._scan_single_row(
                        0, stop_event, user_setting, icon_x_list, icon_y_list
                    )
                elif all_dup:
                    logger.debug(
                        "Skip page flip overscroll correction: disabled by user setting"
                    )
                # 扫描剩余行（第 2-5 行）
                self._scan_current_page(
                    stop_event,
                    user_setting,
                    icon_x_list,
                    icon_y_list,
                    start_row_index=1,
                )
            else:
                # 首页：从第一行开始扫描
                self._scan_current_page(
                    stop_event,
                    user_setting,
                    icon_x_list,
                    icon_y_list,
                    start_row_index=0,
                )

            # 如果已经扫描完最后一页，停止扫描
            if is_last_page:
                logger.info("已扫描完最后一页，基质扫描完成。")
                scan_completed_naturally = True
                break

            # 检查停止事件
            if stop_event.is_set():
                logger.info("基质扫描被中断，停止翻页操作。")
                break

            # 执行渐进式拖动翻页
            logger.info("开始渐进式拖动翻页...")
            row_height = icon_y_list[1] - icon_y_list[0] if len(icon_y_list) > 1 else 0
            progressive_drag_distance, is_last_page = self._progressive_drag(
                drag_start,
                drag_end,
                scrollbar_pos,
                stop_event,
                step=50,  # 每次拖动50像素
                max_drag=max_drag_distance,
                row_height=row_height,
            )

            if is_last_page:
                logger.info(
                    f"检测到滚动条到底，已渐进滚动 {progressive_drag_distance}px，下一页将是最后一页。"
                )
            else:
                if user_setting.fix_grid_row_offset_after_page_flip:
                    self._align_grid_rows_after_drag(
                        drag_start, icon_x_list, icon_y_list
                    )
                else:
                    logger.debug(
                        "Skip row alignment after page drag: disabled by user setting"
                    )
                if scrollbar_pos and self._check_scrollbar_at_bottom(scrollbar_pos):
                    is_last_page = True
                    logger.info("行对齐微调后检测到滚动条到底，下一页将作为最后一页。")

        if page_count >= max_pages:
            logger.info(f"已达到最大页数限制 ({max_pages})，扫描停止。")

        # 冗余清理（实验性）：按触发模式执行
        self._maybe_run_cleanup(scan_completed_naturally, stop_event, user_setting)

        logger.info("基质扫描完成。")

        # 输出武器基质数量统计
        logger.info(f"共扫描了 {self._total_essence_count} 个基质。")
        display_counts = self._get_display_essence_counts()
        if display_counts:
            # 按 稀有度降序 武器ID 排序
            def sort_key(item: tuple[WeaponId, int]) -> tuple[int, WeaponId]:
                weapon_id, _ = item
                weapon = self.ctx.static_game_data.get_weapon(weapon_id)
                # 负数使稀有度按降序排序
                rarity = -weapon.rarity if weapon else 0
                return (rarity, weapon_id)

            sorted_counts = sorted(display_counts.items(), key=sort_key)

            logger.info("武器基质数量统计：")
            for weapon_id, count in sorted_counts:
                weapon = self.ctx.static_game_data.get_weapon(weapon_id)
                if weapon:
                    weapon_type = self.ctx.static_game_data.get_weapon_type(
                        weapon.weapon_type
                    )
                    type_name = weapon_type.name if weapon_type else "未知类型"
                    rarity_color = self.ctx.static_game_data.get_rarity_color(
                        weapon.rarity
                    )
                    logger.opt(colors=True).info(
                        f"  <fg {rarity_color}><bold>{weapon.name}（{weapon.rarity}★ {type_name}）</></>: {count} 个基质"
                    )
                else:
                    logger.opt(colors=True).info(
                        f"  <bold>{weapon_id}</>: {count} 个基质"
                    )
        elif self._total_essence_count > 0:
            # 扫描了基质但没有匹配到任何武器
            logger.info("没有匹配到任何非垃圾武器。")

    def _scan_current_page(
        self,
        stop_event: threading.Event,
        user_setting: UserSetting,
        icon_x_list: list[int],
        icon_y_list: list[int],
        start_row_index: int = 0,
    ) -> None:
        """
        扫描当前页的所有基质。

        Args:
            start_row_index: 开始扫描的行索引（0表示从第一行开始）
        """
        # 从指定行开始扫描
        rows_to_scan = list(enumerate(icon_y_list))[start_row_index:]

        for i, relative_y in rows_to_scan:
            for j, relative_x in enumerate(icon_x_list):
                if not self._window_actions.target_is_active:
                    logger.info("终末地窗口不在前台，停止基质扫描。")
                    return

                if stop_event.is_set():
                    logger.info("基质扫描被中断。")
                    return

                logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

                # 点击基质图标位置
                self._window_actions.click(relative_x, relative_y)
                self._window_actions.wait(0.3)

                # 识别基质信息
                data = recognize_essence(
                    self._image_source,
                    self.ctx,
                    self._profile,
                )

                if (
                    data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                    or data.lock_label == LockStatusLabel.MAYBE_LOCKED
                ):
                    continue

                # 记录基质指纹用于翻页去重检测
                self._scanned_essence_hashes.add(self._get_essence_hash(data))

                # 预先获取所有武器的优先级排序，传递给 evaluate 函数
                all_weapon_ids = set(self._weapon_essence_counts.keys()) | set(
                    self._weapon_essence_levels.keys()
                )
                for w in self.ctx.static_game_data.list_weapons():
                    all_weapon_ids.add(w.weapon_id)
                weapon_priority_order = self._sort_weapons_by_priority(all_weapon_ids)

                # Layer 1: 分类
                classification = classify_essence(
                    data, user_setting, self.ctx.static_game_data
                )

                # Layer 2: 认领
                claim_result = self._claim_context.claim(
                    classification,
                    data,
                    user_setting,
                    weapon_essence_levels=self._weapon_essence_levels,
                    weapon_priority_order=weapon_priority_order,
                    static_game_data=self.ctx.static_game_data,
                )

                # Layer 3: 组装 log_message
                evaluation = build_evaluation_result(
                    classification,
                    claim_result,
                    self.ctx.static_game_data,
                    user_setting,
                    weapon_priority_order=weapon_priority_order,
                )

                # 统计基质总数（跳过 SKIP 的基质）
                if evaluation.quality != EssenceQuality.SKIP:
                    self._total_essence_count += 1

                # 冗余清理（实验性）：记录本轮判为宝藏的基质
                if (
                    self._cleanup_active
                    and evaluation.quality == EssenceQuality.TREASURE
                ):
                    self._record_cleanup_claim(
                        claim_result,
                        data,
                        page=self._cleanup_page_index,
                        row=i,
                        col=j,
                    )

                # 同步认领结果到引擎
                for weapon_id, levels in claim_result.updated_levels.items():
                    self._weapon_essence_levels[weapon_id] = levels
                    count = self._claim_context.treasure_counts.get(weapon_id, 0)
                    if count > 0:
                        self._weapon_essence_counts[weapon_id] = count

                for weapon_id, levels in claim_result.cascade_updated.items():
                    self._weapon_essence_levels[weapon_id] = levels
                    count = self._claim_context.treasure_counts.get(weapon_id, 0)
                    if count > 0:
                        self._weapon_essence_counts[weapon_id] = count

                if (
                    evaluation.quality == EssenceQuality.TRASH
                    and evaluation.matched_weapons
                ):
                    logger.opt(colors=True).warning(evaluation.log_message)
                else:
                    logger.opt(colors=True).success(evaluation.log_message)

                if evaluation.stop_scan:
                    logger.info("已根据设置结束本次基质扫描。")
                    stop_event.set()
                    return

                actions = decide_actions(data, evaluation, user_setting)

                for action in actions:
                    if action.type == ActionType.CLICK_LOCK:
                        pos = self._profile.LOCK_BUTTON_POS
                        self._window_actions.click(pos.x, pos.y)
                    elif action.type == ActionType.CLICK_ABANDON:
                        pos = self._profile.DEPRECATE_BUTTON_POS
                        self._window_actions.click(pos.x, pos.y)

                    self._window_actions.wait(0.3)
                    logger.opt(colors=True).success(
                        f"<LIGHT-YELLOW><bold>{action.log_message}</></>"
                    )

    def _check_scrollbar_at_bottom(self, check_pos: Point) -> bool:
        """
        检测滚动条是否已到达底部。

        在像素区域内检测是否有亮点（RGB 都高于 100），
        如果检测到亮点则认为是滚动条，表明已到达底部。

        Args:
            check_pos: 检测位置（像素坐标）

        Returns:
            True 如果检测到滚动条（已到达底部），False 否则
        """
        try:
            # 根据分辨率计算搜索半径（1080p 为 2，其他分辨率按比例缩放）
            resolution = self._profile.RESOLUTION
            scale_factor = resolution[1] / 1080
            radius = max(1, round(2 * scale_factor))

            # 截取检测位置附近的区域
            roi = Region(
                Point(check_pos.x - radius, check_pos.y - radius),
                Point(check_pos.x + radius + 1, check_pos.y + radius + 1),
            )
            screenshot = self._image_source.screenshot(roi)

            # 在区域内查找是否有亮点（BGR 三通道都高于 100）
            has_bright = bool(np.any(np.all(screenshot[:, :, :3] > 100, axis=2)))
            if has_bright:
                logger.info(f"检测到滚动条亮点 at ({check_pos.x}, {check_pos.y})")
                return True

            logger.debug(f"未检测到滚动条亮点 at ({check_pos.x}, {check_pos.y})")
            return False

        except Exception as e:
            logger.warning(f"滚动条检测失败: {e}")
            return False

    def _check_scrollbar_at_top(self) -> bool:
        """检测滚动条是否已回到顶部（冗余清理回页首用）。

        与 _check_scrollbar_at_bottom 对称：检测 SCROLLBAR_TOP_CHECK_POS
        附近是否有亮点（滑块顶端），有则说明已滚动到第一页。
        """
        check_pos = self._profile.SCROLLBAR_TOP_CHECK_POS
        try:
            # 根据分辨率计算搜索半径（1080p 为 2，其他分辨率按比例缩放）
            resolution = self._profile.RESOLUTION
            scale_factor = resolution[1] / 1080
            radius = max(1, round(2 * scale_factor))

            roi = Region(
                Point(check_pos.x - radius, check_pos.y - radius),
                Point(check_pos.x + radius + 1, check_pos.y + radius + 1),
            )
            screenshot = self._image_source.screenshot(roi)

            has_bright = bool(np.any(np.all(screenshot[:, :, :3] > 100, axis=2)))
            if has_bright:
                logger.debug(f"检测到滚动条顶部亮点 at ({check_pos.x}, {check_pos.y})")
                return True

            logger.debug(f"未检测到滚动条顶部亮点 at ({check_pos.x}, {check_pos.y})")
            return False

        except Exception as e:
            logger.warning(f"滚动条顶部检测失败: {e}")
            return False

    def _reset_to_first_page(self, stop_event: threading.Event) -> bool:
        """冗余清理：滚动条顶端 16px 上拖，配合顶部亮点检测回到第一页。

        拖动距离恒定 16px（不随分辨率缩放，过小可能无法被游戏识别）；
        起点随分辨率缩放。本轮从未翻页时无需确认（物理上就在第一页）；
        翻过页但 3 次尝试仍未确认回到顶部时放弃清理——不能按假定页码
        继续，指纹校验无法区分相同内容的基质。
        """
        if not self._cleanup_flipped_pages:
            logger.debug("冗余清理：本轮未翻页，直接按第一页处理。")
            return True

        top = self._profile.SCROLLBAR_TOP_CHECK_POS
        start = Point(top.x, top.y + _SCROLL_TOP_DRAG_PX)

        if self._check_scrollbar_at_top():
            logger.debug("冗余清理：已在第一页。")
            return True

        for attempt in range(1, 4):
            if stop_event.is_set():
                return False
            self._window_actions.progressive_drag(
                start.x,
                start.y,
                top.x,
                top.y,
                step=8,
                max_drag=_SCROLL_TOP_DRAG_PX,
            )
            self._window_actions.wait(0.5)
            if self._check_scrollbar_at_top():
                logger.info(f"冗余清理：已回到第一页（第 {attempt} 次尝试）。")
                return True

        logger.warning("冗余清理：3 次尝试未确认回到第一页，放弃本次清理。")
        return False

    def _advance_to_page(
        self,
        current_page: int,
        target_page: int,
        stop_event: threading.Event,
        user_setting: UserSetting,
    ) -> bool:
        """冗余清理：从当前页向前翻页到目标页，完全复用扫描时的翻页机件。

        与扫描翻页保持同一路径（渐进拖动 + 行末检测 + 暗带对齐），保证
        回访页的网格行偏移与扫描时一致；到达扫描期执行过过冲校正的页时
        重放同参数的 3/4 行校正。提前检测到列表底部时，仅当目标页就是
        最后扫描页（_cleanup_max_page）才视为到达，否则翻页序列已发散，
        放弃本次清理。
        """
        drag_start = self._profile.DRAG_START_POS
        drag_end = self._profile.DRAG_END_POS
        scrollbar_pos = self._profile.SCROLLBAR_CHECK_POS
        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        row_height = icon_y_list[1] - icon_y_list[0] if len(icon_y_list) > 1 else 0
        max_drag_distance = (
            int((drag_end.x - drag_start.x) ** 2 + (drag_end.y - drag_start.y) ** 2)
            ** 0.5
        )

        pages_remaining = target_page - current_page
        for _ in range(pages_remaining):
            if stop_event.is_set() or not self._window_actions.target_is_active:
                logger.warning("冗余清理：翻页中止。")
                return False
            logger.debug("冗余清理：向前翻页。")
            _distance, is_last_page = self._progressive_drag(
                drag_start,
                drag_end,
                scrollbar_pos,
                stop_event,
                step=50,
                max_drag=max_drag_distance,
                row_height=row_height,
            )
            if is_last_page:
                # 提前到底：物理位置即最后扫描页，仅当目标页就是它时视为到达
                if target_page != self._cleanup_max_page:
                    logger.warning(
                        f"冗余清理：翻页提前到达列表底部，但目标为第 {target_page} 页"
                        f"（最后扫描页为第 {self._cleanup_max_page} 页），放弃本次清理。"
                    )
                    return False
                break
            if user_setting.fix_grid_row_offset_after_page_flip:
                self._align_grid_rows_after_drag(drag_start, icon_x_list, icon_y_list)
            if self._check_scrollbar_at_bottom(scrollbar_pos):
                # 同提前到底处理：翻页后检测到底部
                if target_page != self._cleanup_max_page:
                    logger.warning(
                        f"冗余清理：翻页后到达列表底部，但目标为第 {target_page} 页"
                        f"（最后扫描页为第 {self._cleanup_max_page} 页），放弃本次清理。"
                    )
                    return False
                break

        # 重放扫描期对该页执行的过冲校正（3/4 行），保证与记录时的网格布局一致
        if target_page in self._cleanup_corrected_pages:
            if row_height > 0:
                self._correct_overscroll(drag_start, round(row_height * 3 / 4))
                logger.debug(f"冗余清理：回放第 {target_page} 页的过冲校正。")
        return True

    def _progressive_drag(
        self,
        drag_start: Point,
        drag_end: Point,
        scrollbar_pos: Point | None,
        stop_event: threading.Event,
        step: int = 50,
        max_drag: int = 800,
        row_height: int = 0,
    ) -> tuple[int, bool]:
        """
        渐进式拖动，使用 WindowActions 接口执行拖动并检测滚动条。

        Args:
            drag_start: 拖动起始位置
            drag_end: 拖动终止位置（目标位置）
            scrollbar_pos: 滚动条检测位置
            stop_event: 停止事件
            step: 每次拖动的像素数
            max_drag: 最大拖动距离
            row_height: 行高（用于计算是否需要额外滚动到整行位置）

        Returns:
            (actual_drag_distance, is_last_page) 实际拖动距离和是否是最后一页
        """

        # 定义滚动条检测回调
        def on_step(step_index: int, screen_x: int, screen_y: int) -> bool:
            """每步回调：检测滚动条是否到底"""
            if stop_event.is_set():
                return True
            if scrollbar_pos and self._check_scrollbar_at_bottom(scrollbar_pos):
                logger.info(f"步 {step_index + 1}: 检测到滚动条到底")
                return True
            return False

        # 使用 WindowActions 执行渐进式拖动
        actual_distance, stopped_early = self._window_actions.progressive_drag(
            drag_start.x,
            drag_start.y,
            drag_end.x,
            drag_end.y,
            step=step,
            max_drag=max_drag,
            on_step=on_step,
        )

        # 如果提前停止，说明检测到滚动条到底
        is_last_page = stopped_early

        if is_last_page:
            logger.info(f"检测到滚动条到底，已拖动 {actual_distance}px")

            # 检测到滚动条到底时，额外多滚动一整行
            # 因为检测点可能正好在倒数第二行，需要确保最后一行完全滚出
            if row_height > 0:
                scrolled_rows = actual_distance / row_height
                # 额外滚动一整行确保滚动到位
                extra_drag = row_height
                logger.info(
                    f"已滚动 {scrolled_rows:.3f} 行，额外滚动一整行 {extra_drag}px 确保到位"
                )
                # 等待惯性滚动停止
                self._window_actions.wait(0.5)
                # 使用 _correct_overscroll 相同的方式执行额外滚动
                self._correct_overscroll(drag_start, extra_drag)
                actual_distance += extra_drag
                logger.info(f"额外滚动完成，总计拖动 {actual_distance}px")
        else:
            # 拖动完成后再次检测滚动条
            if scrollbar_pos and self._check_scrollbar_at_bottom(scrollbar_pos):
                is_last_page = True
                logger.info(f"拖动完成后检测到滚动条到底，总计拖动 {actual_distance}px")

        return actual_distance, is_last_page

    def _calculate_skip_rows(
        self,
        actual_drag: int,
        row_height: int,
        total_rows: int,
    ) -> int:
        """
        根据渐进滚动距离与行高计算需要跳过的行数。

        Args:
            actual_drag: 实际滚动距离
            row_height: 行高
            total_rows: 当前页总行数

        Returns:
            需要跳过的行数
        """
        if row_height <= 0 or actual_drag <= 0:
            return 0

        # 计算滚动行数，使用 ceil 向上取整确保滚动到位
        # 例如：2.1、2.5、2.9 都会取整为 3，多滚动一行确保内容完全滚出
        # 松开鼠标后页面会自动回弹到正确位置
        # 减 1 抵消 _progressive_drag 中额外滚动一整行造成的多算
        scrolled_rows = max(0, math.ceil(actual_drag / row_height) - 1)
        skip_rows = total_rows - scrolled_rows

        logger.info(
            f"计算跳过行数: 实际滚动={actual_drag}px，行高={row_height}px，"
            f"滚动行数={actual_drag / row_height:.3f}→{scrolled_rows}，跳过={skip_rows}行"
        )

        return skip_rows

    def _align_grid_rows_after_drag(
        self,
        drag_start: Point,
        icon_x_list: list[int],
        icon_y_list: list[int],
    ) -> None:
        """翻页拖动后检测网格行偏移并执行微调修正。"""
        if len(icon_y_list) < 2 or not icon_x_list:
            logger.debug("跳过行对齐：网格坐标不足")
            return

        row_height = icon_y_list[1] - icon_y_list[0]
        if row_height <= 0:
            logger.debug("跳过行对齐：无效行高={}", row_height)
            return

        offset = self._detect_grid_row_offset(icon_x_list, icon_y_list, row_height)
        if offset is None:
            return

        # 偏移量太小则忽略，避免视觉抖动
        min_adjust = max(10, round(row_height * 0.08))
        if abs(offset) < min_adjust:
            logger.debug("行对齐偏移={}px，无需修正", offset)
            return

        max_adjust = round(row_height * 0.45)
        adjust = max(-max_adjust, min(max_adjust, offset))
        if adjust != offset:
            logger.debug(
                "行对齐修正已限制：原始偏移={}px，实际修正={}px",
                offset,
                adjust,
            )

        # offset > 0 表示暗带实际位置比期望低，内容下移，需向上拖动修正
        # 因此拖动方向为 Y - adjust（向上为负方向）
        logger.info(
            "翻页后行对齐修正：偏移={}px，修正={}px（向上拖动）",
            offset,
            adjust,
        )
        # 使用小步长分多步拖动，确保游戏窗口能正确识别为拖动而非点击
        # step 必须小于 adjust，否则 progressive_drag 只会执行 1 步
        self._window_actions.progressive_drag(
            drag_start.x,
            drag_start.y,
            drag_start.x,
            drag_start.y - adjust,
            step=max(3, abs(adjust) // 5),
            max_drag=abs(adjust),
        )
        self._window_actions.wait(0.25)

    # 暗带检测阈值：间隙行的平均亮度远低于卡片区域（间隙 < 25，卡片 > 50）
    _GAP_BRIGHTNESS_THRESHOLD: float = 40.0
    # 连续暗行归为同一条暗带的最大间距（像素）
    _GAP_BAND_GROUP_DISTANCE: int = 5
    # 暗带间距与期望行高匹配时的最大偏差（像素），用于过滤噪声暗带
    _GAP_SPACING_TOLERANCE: int = 25

    def _detect_grid_row_offset(
        self,
        icon_x_list: list[int],
        icon_y_list: list[int],
        row_height: int,
    ) -> int | None:
        """通过检测卡片行之间的暗带（间隙）来估算网格行偏移量。

        原理：游戏界面中，相邻卡片行之间存在约 9px 厚的纯黑暗带（亮度 < 25），
        间距恒定等于 row_height。通过定位暗带的实际 Y 坐标并与期望位置比较，
        即可精确计算出翻页后的行偏移。

        Args:
            icon_x_list: 基质图标列坐标列表（用于确定截图水平范围）。
            icon_y_list: 基质图标行坐标列表（用于计算期望间隙位置）。
            row_height: 相邻行中心的间距（像素）。

        Returns:
            检测到的偏移量（像素），未检测到时返回 None。
        """
        card_half = row_height // 2
        # 期望间隙中心：相邻两行之间，上行底部与下行顶部的中点
        expected_gap_centers: list[float] = []
        for gap_index in range(len(icon_y_list) - 1):
            gap_center = (
                icon_y_list[gap_index]
                + card_half
                + icon_y_list[gap_index + 1]
                - card_half
            ) / 2.0
            expected_gap_centers.append(gap_center)

        if not expected_gap_centers:
            logger.debug("跳过间隙检测：不足 2 行")
            return None

        # 截取网格区域（避开左右边缘 UI 干扰，取卡片列跨度内侧）
        x_min = max(0, min(icon_x_list) - 20)
        x_max = max(icon_x_list) + 20 + 1
        client_width, client_height = self._image_source.get_client_size()
        x_max = min(client_width, x_max)

        # 垂直范围：从首行上方到末行下方，留出 margin
        margin = row_height
        y_min = max(0, min(icon_y_list) - margin)
        y_max = min(client_height, max(icon_y_list) + margin + 1)

        if x_max <= x_min or y_max <= y_min:
            return None

        try:
            screenshot = self._image_source.screenshot(
                Region(Point(x_min, y_min), Point(x_max, y_max))
            )
        except Exception as exc:
            logger.debug("间隙检测截图失败：{}", exc)
            return None

        if screenshot.size == 0:
            return None

        # 计算每行的平均亮度（取 RGB 三通道均值）
        gray = screenshot[:, :, :3].astype(np.float32).mean(axis=(1, 2))

        # 找出亮度低于阈值的暗行
        dark_rows: list[int] = []
        for row_index in range(len(gray)):
            if gray[row_index] < self._GAP_BRIGHTNESS_THRESHOLD:
                dark_rows.append(row_index)

        if not dark_rows:
            logger.debug(
                "间隙检测：未找到暗行（阈值={}）", self._GAP_BRIGHTNESS_THRESHOLD
            )
            return None

        # 将连续暗行分组为暗带（间隙），间距超过阈值则断开
        gap_bands: list[tuple[int, int]] = []
        band_start = dark_rows[0]
        band_prev = dark_rows[0]
        for row_index in dark_rows[1:]:
            if row_index - band_prev > self._GAP_BAND_GROUP_DISTANCE:
                gap_bands.append((band_start, band_prev))
                band_start = row_index
            band_prev = row_index
        gap_bands.append((band_start, band_prev))

        # 取每条暗带的中心 Y（转换为截图全局坐标）
        actual_gap_centers = [
            (band_top + band_bottom) / 2.0 + y_min
            for band_top, band_bottom in gap_bands
        ]

        logger.debug(
            "间隙检测：找到 {} 条暗带，y={}，期望 {} 个间隙",
            len(gap_bands),
            [round(c) for c in actual_gap_centers],
            len(expected_gap_centers),
        )

        # 用相对间距过滤噪声暗带：相邻暗带间距应约等于 row_height
        # 这样即使整体偏移很大，只要间距正确就能识别出真正的行间隙
        spacing_tol = self._GAP_SPACING_TOLERANCE
        valid_centers: list[float] = []
        for i in range(len(gap_bands)):
            band_top, band_bottom = gap_bands[i]
            band_center = (band_top + band_bottom) / 2.0 + y_min
            # 检查与前后暗带的间距是否约等于 row_height
            has_valid_neighbor = False
            if i > 0:
                prev_top, prev_bottom = gap_bands[i - 1]
                prev_center = (prev_top + prev_bottom) / 2.0 + y_min
                if abs((band_center - prev_center) - row_height) <= spacing_tol:
                    has_valid_neighbor = True
            if i < len(gap_bands) - 1:
                next_top, next_bottom = gap_bands[i + 1]
                next_center = (next_top + next_bottom) / 2.0 + y_min
                if abs((next_center - band_center) - row_height) <= spacing_tol:
                    has_valid_neighbor = True
            if has_valid_neighbor:
                valid_centers.append(band_center)

        logger.debug(
            "间隙检测：{} 条暗带，y={}，期望 {} 个间隙，{} 条间距有效",
            len(gap_bands),
            [round((t + b) / 2.0 + y_min) for t, b in gap_bands],
            len(expected_gap_centers),
            len(valid_centers),
        )

        if not valid_centers:
            logger.debug(
                "间隙检测：无暗带间距匹配行高（±{}px）",
                spacing_tol,
            )
            return None

        # 对每条有效暗带，找最近的期望间隙，计算偏移量
        offsets: list[float] = []
        for actual_center in valid_centers:
            best_distance = float("inf")
            best_offset = 0.0
            for expected_center in expected_gap_centers:
                distance = abs(actual_center - expected_center)
                if distance < best_distance:
                    best_distance = distance
                    best_offset = actual_center - expected_center
            offsets.append(best_offset)

        if not offsets:
            return None

        # 取中位数作为最终偏移量（抵抗个别异常值）
        offsets.sort()
        median_offset = offsets[len(offsets) // 2]
        result = round(median_offset)

        logger.debug(
            "间隙检测：偏移列表={}，中位数={:.1f}，结果={}",
            [round(o) for o in offsets],
            median_offset,
            result,
        )
        return result

    def _scan_single_row(
        self,
        row_index: int,
        stop_event: threading.Event,
        user_setting: UserSetting,
        icon_x_list: list[int],
        icon_y_list: list[int],
    ) -> bool:
        """
        扫描指定的单行基质（含识别、评估、操作），并返回是否全部是已扫描过的基质。

        Args:
            row_index: 行索引
            stop_event: 停止事件
            user_setting: 用户设置
            icon_x_list: 列 X 坐标列表
            icon_y_list: 行 Y 坐标列表

        Returns:
            True 如果该行所有可识别基质都是已扫描过的（全部重复），False 否则
        """
        y = icon_y_list[row_index]
        found_any = False
        all_duplicates = True

        for j, relative_x in enumerate(icon_x_list):
            if not self._window_actions.target_is_active:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                return False

            if stop_event.is_set():
                logger.info("基质扫描被中断。")
                return False

            logger.info(f"正在扫描第 {row_index + 1} 行第 {j + 1} 列的基质...")

            self._window_actions.click(relative_x, y)
            self._window_actions.wait(0.3)

            data = recognize_essence(
                self._image_source,
                self.ctx,
                self._profile,
            )

            if (
                data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or data.lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                continue

            found_any = True
            fingerprint = self._get_essence_hash(data)
            is_dup = fingerprint in self._scanned_essence_hashes
            self._scanned_essence_hashes.add(fingerprint)

            if not is_dup:
                all_duplicates = False

            # 预先获取所有武器的优先级排序，传递给 evaluate 函数
            all_weapon_ids = set(self._weapon_essence_counts.keys()) | set(
                self._weapon_essence_levels.keys()
            )
            for w in self.ctx.static_game_data.list_weapons():
                all_weapon_ids.add(w.weapon_id)
            weapon_priority_order = self._sort_weapons_by_priority(all_weapon_ids)

            # Layer 1: 分类
            classification = classify_essence(
                data, user_setting, self.ctx.static_game_data
            )

            # Layer 2: 认领
            claim_result = self._claim_context.claim(
                classification,
                data,
                user_setting,
                weapon_essence_levels=self._weapon_essence_levels,
                weapon_priority_order=weapon_priority_order,
                static_game_data=self.ctx.static_game_data,
            )

            # Layer 3: 组装 log_message
            evaluation = build_evaluation_result(
                classification,
                claim_result,
                self.ctx.static_game_data,
                user_setting,
                weapon_priority_order=weapon_priority_order,
            )

            if evaluation.quality != EssenceQuality.SKIP:
                self._total_essence_count += 1

            # 冗余清理（实验性）：记录本轮判为宝藏的基质
            if self._cleanup_active and evaluation.quality == EssenceQuality.TREASURE:
                self._record_cleanup_claim(
                    claim_result,
                    data,
                    page=self._cleanup_page_index,
                    row=row_index,
                    col=j,
                )

            # 同步认领结果到引擎
            for weapon_id, levels in claim_result.updated_levels.items():
                self._weapon_essence_levels[weapon_id] = levels
                count = self._claim_context.treasure_counts.get(weapon_id, 0)
                if count > 0:
                    self._weapon_essence_counts[weapon_id] = count

            for weapon_id, levels in claim_result.cascade_updated.items():
                self._weapon_essence_levels[weapon_id] = levels
                count = self._claim_context.treasure_counts.get(weapon_id, 0)
                if count > 0:
                    self._weapon_essence_counts[weapon_id] = count

            if (
                evaluation.quality == EssenceQuality.TRASH
                and evaluation.matched_weapons
            ):
                logger.opt(colors=True).warning(evaluation.log_message)
            else:
                logger.opt(colors=True).success(evaluation.log_message)

            if evaluation.stop_scan:
                logger.info("已根据设置结束本次基质扫描。")
                stop_event.set()
                return False

            actions = decide_actions(data, evaluation, user_setting)

            for action in actions:
                if action.type == ActionType.CLICK_LOCK:
                    pos = self._profile.LOCK_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                elif action.type == ActionType.CLICK_ABANDON:
                    pos = self._profile.DEPRECATE_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)

                self._window_actions.wait(0.3)
                logger.opt(colors=True).success(
                    f"<LIGHT-YELLOW><bold>{action.log_message}</></>"
                )

        # 有可识别基质且全部重复时返回 True
        return found_any and all_duplicates

    def _correct_overscroll(
        self,
        drag_start: Point,
        adjust_distance: int,
    ) -> None:
        """
        向上微调指定距离，修正翻页过量。

        与翻页方向相同（从下往上拖），使内容再向下滚动。

        Args:
            drag_start: 拖动起始位置（与翻页相同）
            adjust_distance: 微调距离（像素）
        """
        logger.info(f"执行微调拖动：向上 {adjust_distance}px")
        self._window_actions.progressive_drag(
            drag_start.x,
            drag_start.y,
            drag_start.x,
            drag_start.y - adjust_distance,
            step=50,
            max_drag=adjust_distance,
        )
        self._window_actions.wait(0.5)
