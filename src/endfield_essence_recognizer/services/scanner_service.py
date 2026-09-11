from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from endfield_essence_recognizer.utils.log import logger


def _format_level(value: int, color: str | None) -> str:
    """格式化单个等级数值，带颜色。"""
    text = f"+{value}"
    if color:
        return f"<fg {color}>{text}</>"
    return text


def _format_levels(affix1: int, affix2: int, affix3: int, static_data: object) -> str:
    """格式化三个词条等级，按规则着色。

    前两个词条: +6→6★色, +5/+4→5★色, +3/+2→4★色, +1→无色
    第三个词条:  +3→6★色, +2→5★色, +1→无色
    """
    c6 = static_data.get_rarity_color(6)
    c5 = static_data.get_rarity_color(5)
    c4 = static_data.get_rarity_color(4)

    def affix_color_12(v: int) -> str | None:
        if v >= 6:
            return c6
        if v >= 4:
            return c5
        if v >= 2:
            return c4
        return None

    def affix_color_3(v: int) -> str | None:
        if v >= 3:
            return c6
        if v >= 2:
            return c5
        return None

    return (
        f"{_format_level(affix1, affix_color_12(affix1))}"
        f"/{_format_level(affix2, affix_color_12(affix2))}"
        f"/{_format_level(affix3, affix_color_3(affix3))}"
    )


if TYPE_CHECKING:
    from collections.abc import Callable

    from endfield_essence_recognizer.core.interfaces import AutomationEngine
    from endfield_essence_recognizer.game_data.models.v2 import WeaponId
    from endfield_essence_recognizer.services.audio_service import AudioService


class ScannerService:
    """
    A service that manages the lifecycle of the AutomationEngine background thread.

    This service ensures thread-safety using an RLock and provides methods to start,
    stop, and toggle the scanning process. It also ensures that only one scanning
    thread is active at a time by joining old threads before starting new ones.
    """

    def __init__(
        self,
        audio_service: AudioService | None = None,
    ) -> None:
        """
        Initialize the ScannerService.

        Args:
            audio_service: Optional AudioService for notification sounds.
        """
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()  # Event to signal the thread to stop
        self._lock = threading.RLock()  # Reentrant lock for nested locking
        self._audio_service = audio_service
        self._current_engine: AutomationEngine | None = None
        self._last_weapon_essence_counts: dict[WeaponId, int] = {}
        self._last_weapon_essence_levels: dict[WeaponId, tuple[int, int, int]] = {}
        self._stopping = False

    def start_scan(self, scanner_factory: Callable[[], AutomationEngine]) -> None:
        """
        Start the scanning process in a background thread.

        If a scan is already running, a warning is logged and nothing happens.
        If a previous thread exists but is dead, it is joined before a new one is started.

        Args:
            scanner_factory: A callable that returns an AutomationEngine instance.
        """
        with self._lock:
            if self._stopping:
                logger.warning("扫描正在停止中。")
                return
            if self.is_running():
                logger.warning("扫描已在运行中。")
                return

            # If there's a dead thread from a previous run, ensure it's joined
            if self._thread is not None:
                self._thread.join()

            logger.debug("正在启动扫描服务...")
            self._stop_event.clear()
            scanner = scanner_factory()
            self._current_engine = scanner

            def wrapped_execute():
                """包装执行逻辑，在完成后触发同步"""
                # 在执行前保存引擎引用，避免竞态条件
                engine_ref = scanner
                try:
                    scanner.execute(self._stop_event)
                finally:
                    # 扫描完成后保存数据并同步（无论是正常完成还是被中断）
                    # 使用保存的引擎引用，而不是 self._current_engine
                    self._on_scan_complete(engine_ref)
                    # 线程退出后复位停止状态。手动停止后紧接着的冗余清理会
                    # 清除停止事件继续运行，停止标记必须在线程真正结束时复位，
                    # 否则 is_running 会永远为 True、后续扫描被拒。
                    with self._lock:
                        if self._thread is threading.current_thread():
                            self._thread = None
                            self._current_engine = None
                        self._stopping = False

            self._thread = threading.Thread(
                target=wrapped_execute,
                daemon=True,
                name="ScannerThread",
            )
            logger.debug("Starting scanner thread.")
            self._thread.start()

            if self._audio_service:
                self._audio_service.play_enable()

    def _on_scan_complete(self, engine: AutomationEngine) -> None:
        """扫描完成后的回调，保存数据并触发同步

        Args:
            engine: 扫描引擎实例（从 wrapped_execute 传入，避免竞态条件）
        """
        logger.info("扫描完成回调被触发")

        from endfield_essence_recognizer.core.scanner.engine import (
            ScannerEngine,
        )

        # 只有 ScannerEngine 才有 get_weapon_essence_data 方法
        if not isinstance(engine, ScannerEngine):
            logger.debug(f"引擎不是 ScannerEngine，跳过数据保存: {type(engine)}")
            return

        # 从引擎获取数据（不需要锁，因为 engine 是局部引用，不会被其他线程访问）
        # 且此时扫描已完成，引擎内部数据不会再被修改
        try:
            data = engine.get_weapon_essence_data()
            logger.debug(
                f"从引擎获取的数据 - counts: {len(data.counts)}, levels: {len(data.levels)}"
            )
        except Exception as e:
            logger.error(f"获取扫描数据失败: {e}", exc_info=True)
            return

        # 在锁内保存数据到实例变量（保护共享状态）
        with self._lock:
            self._last_weapon_essence_counts = data.counts
            self._last_weapon_essence_levels = data.levels
            # 在锁内复制数据，确保数据一致性
            data_to_sync = data.levels.copy()

        logger.info(f"获取到扫描数据: {len(data_to_sync)} 把武器")

        # 在锁外触发同步，避免死锁
        # _sync_to_treasure_matrix 可能调用其他服务（如 profile_manager），
        # 这些服务可能有自己的锁，在持有 self._lock 时调用可能导致死锁
        if data_to_sync:
            logger.info(f"开始同步 {len(data_to_sync)} 把武器到宝藏基质配置")
            try:
                self._sync_to_treasure_matrix(data_to_sync)
                # 通知前端刷新宝藏基质/基质规划等依赖 profiles 的页面
                from endfield_essence_recognizer.dependencies import (
                    get_event_service,
                )
                from endfield_essence_recognizer.services.event_service import (
                    EVENT_PROFILES_CHANGED,
                )

                get_event_service().publish({"type": EVENT_PROFILES_CHANGED})
            except Exception as e:
                logger.error(f"同步扫描数据失败: {e}", exc_info=True)
        else:
            logger.warning("没有数据需要同步")

    def stop_scan(self) -> None:
        """
        Stop the scanning process.

        Sets the stop event and waits for the background thread to join.
        If no scan is running, a warning is logged.
        """
        thread_to_join = None
        with self._lock:
            if not self.is_running():
                logger.warning("扫描未在运行。")
                return

            logger.debug("正在停止扫描服务...")
            self._stopping = True
            self._stop_event.set()
            thread_to_join = self._thread

        # 在锁外等待线程结束，避免死锁
        if thread_to_join is not None:
            thread_to_join.join(timeout=5.0)
            if thread_to_join.is_alive():
                logger.warning("扫描线程未在超时时间内停止")
                return
            logger.debug("Scanner thread joined.")

        with self._lock:
            if self._thread is thread_to_join:
                self._thread = None
                self._current_engine = None
            self._stopping = False

        if self._audio_service:
            self._audio_service.play_disable()

    def is_running(self) -> bool:
        """
        Check if the scanning thread is currently alive.

        Returns:
            True if the thread is active, False otherwise.
        """
        with self._lock:
            return self._stopping or (
                self._thread is not None and self._thread.is_alive()
            )

    def get_current_engine(self) -> AutomationEngine | None:
        """
        Get the current engine instance.

        Returns:
            The current engine instance, or None if no engine is running.
        """
        with self._lock:
            return self._current_engine

    def get_weapon_essence_counts(self) -> dict[WeaponId, int]:
        """
        Get the weapon essence counts.

        Returns the real-time data from the currently running scan if a ScannerEngine
        task is active, or the data from the last finished scan otherwise.

        Returns:
            A dictionary mapping weapon IDs to essence counts.
        """
        with self._lock:
            # 如果当前有正在运行的 ScannerEngine，返回实时数据
            if self._current_engine is not None:
                from endfield_essence_recognizer.core.scanner.engine import (
                    ScannerEngine,
                )

                if isinstance(self._current_engine, ScannerEngine):
                    return self._current_engine.get_weapon_essence_counts()

            # 否则返回最后一次扫描的数据
            return self._last_weapon_essence_counts.copy()

    def get_weapon_essence_data(self):
        """
        获取完整的武器基质数据（包括等级）。

        Returns:
            WeaponEssenceData 对象，包含计数和等级信息。
        """
        from endfield_essence_recognizer.schemas.scanner import WeaponEssenceData

        with self._lock:
            # 如果当前有正在运行的 ScannerEngine，返回实时数据
            if self._current_engine is not None:
                from endfield_essence_recognizer.core.scanner.engine import (
                    ScannerEngine,
                )

                if isinstance(self._current_engine, ScannerEngine):
                    return self._current_engine.get_weapon_essence_data()

            # 否则返回最后一次扫描的数据
            return WeaponEssenceData(
                counts=self._last_weapon_essence_counts.copy(),
                levels=self._last_weapon_essence_levels.copy(),
            )

    def _sync_to_treasure_matrix(
        self, weapon_levels: dict[str, tuple[int, int, int]]
    ) -> None:
        """同步扫描数据到宝藏基质配置

        Args:
            weapon_levels: 武器ID到等级元组的映射
        """
        logger.info(f"开始同步扫描数据，共 {len(weapon_levels)} 把武器")
        try:
            # 延迟导入避免循环依赖
            from endfield_essence_recognizer.api.routes.profiles import (
                get_profile_manager,
            )
            from endfield_essence_recognizer.dependencies import (
                default_user_setting_manager,
                get_static_game_data,
            )
            from endfield_essence_recognizer.schemas.profile import (
                CUSTOM_ID_PREFIX,
                TreasureMatrixEntry,
            )

            profile_manager = get_profile_manager()
            static_data = get_static_game_data()

            # 自定义基质 ID → 显示名称，用于落盘缓存与日志展示
            custom_names = {
                f"{CUSTOM_ID_PREFIX}{ts.id}": (ts.name or "未命名")
                for ts in default_user_setting_manager()
                .get_user_setting()
                .treasure_essence_stats
                if ts.id
            }

            logger.info("获取到 profile_manager 和 static_data")

            entries: list[TreasureMatrixEntry] = []
            for weapon_id, levels in weapon_levels.items():
                weapon = static_data.get_weapon(weapon_id)
                if weapon:
                    weapon_name = weapon.name
                elif weapon_id.startswith(CUSTOM_ID_PREFIX):
                    weapon_name = custom_names.get(weapon_id, weapon_id)
                else:
                    weapon_name = weapon_id
                logger.debug(f"处理武器 {weapon_name}({weapon_id}), 等级: {levels}")

                # 新增满级武器默认不参与计算，避免扫描后把已毕业武器加入刷取建议。
                is_maxed = levels[0] == 6 and levels[1] == 6 and levels[2] == 3
                entries.append(
                    TreasureMatrixEntry(
                        weapon_id=weapon_id,
                        weapon_name=weapon_name,
                        affix1_level=levels[0],
                        affix2_level=levels[1],
                        affix3_level=levels[2],
                        include_in_calculation=not is_maxed,
                    )
                )

            sync_result = profile_manager.sync_treasure_matrix_entries(entries)

            def log_synced_entry(entry: TreasureMatrixEntry, *, is_added: bool) -> None:
                """统一输出新增/更新日志，避免两处格式漂移。"""
                if entry.weapon_id.startswith(CUSTOM_ID_PREFIX):
                    # 自定义基质沿用扫描日志的橙色（六星色）样式
                    weapon_text = (
                        f"<fg #FF7100><bold>{entry.weapon_name or entry.weapon_id}"
                        "（自定义基质）</></>"
                    )
                else:
                    weapon = static_data.get_weapon(entry.weapon_id)
                    rarity_color = (
                        static_data.get_rarity_color(weapon.rarity)
                        if weapon
                        else "#FFFFFF"
                    )
                    weapon_type = (
                        static_data.get_weapon_type(weapon.weapon_type)
                        if weapon
                        else None
                    )
                    type_name = weapon_type.name if weapon_type else "未知类型"
                    rarity_label = (
                        f"{weapon.rarity}★ {type_name}" if weapon else type_name
                    )
                    weapon_name = entry.weapon_name or (
                        weapon.name if weapon else entry.weapon_id
                    )
                    weapon_text = f"<fg {rarity_color}><bold>{weapon_name}（{rarity_label}）</></>"
                level_text = _format_levels(
                    entry.affix1_level,
                    entry.affix2_level,
                    entry.affix3_level,
                    static_data,
                )
                if is_added:
                    logger.opt(colors=True).info(
                        f"已将武器 {weapon_text} 添加到宝藏基质配置，等级: {level_text}"
                    )
                else:
                    logger.opt(colors=True).info(
                        f"已更新武器 {weapon_text} 的等级: {level_text}"
                    )

            for entry in sync_result.added:
                log_synced_entry(entry, is_added=True)
            for entry in sync_result.updated:
                log_synced_entry(entry, is_added=False)

            logger.info(
                f"扫描数据同步完成: 新增 {len(sync_result.added)} 把武器，更新 {len(sync_result.updated)} 把武器"
            )
        except Exception as e:
            logger.error(f"同步扫描数据到宝藏基质配置失败: {e}", exc_info=True)

    def toggle_scan(self, scanner_factory: Callable[[], AutomationEngine]) -> None:
        """
        Toggle the scanning state.

        Starts the scan if it's not running, or stops it if it is.

        Args:
            scanner_factory: A callable that returns an AutomationEngine instance. Called if starting a scan.
        """
        # 检查状态，但不在锁内调用 start/stop，避免死锁
        should_stop = self.is_running()

        if should_stop:
            self.stop_scan()
        else:
            self.start_scan(scanner_factory)
