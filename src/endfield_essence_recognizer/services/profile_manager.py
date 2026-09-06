"""
账号管理服务。

管理多账号及其宝藏基质配置。
账号存储在主配置文件旁的 JSON 文件中。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from json import JSONDecodeError
from typing import TYPE_CHECKING

from pydantic import ValidationError

from endfield_essence_recognizer.schemas.profile import (
    AFFIX1_MAX_LEVEL,
    AFFIX2_MAX_LEVEL,
    AFFIX3_MAX_LEVEL,
    CUSTOM_ID_PREFIX,
    DEFAULT_PROFILE_NAME,
    LEGACY_CUSTOM_ID_PREFIX,
    ProfileCollection,
    ProfileData,
    TreasureMatrixEntry,
)
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = [
    "ProfileLoadError",
    "ProfileManager",
    "ProfileSaveError",
    "TreasureMatrixSyncResult",
]


class ProfileLoadError(RuntimeError):
    """账号配置文件存在但无法安全加载。"""


class ProfileSaveError(RuntimeError):
    """账号配置文件无法安全保存。"""


@dataclass(frozen=True)
class TreasureMatrixSyncResult:
    """扫描数据同步到宝藏基质后的变更摘要。"""

    profile: ProfileData
    added: list[TreasureMatrixEntry]
    updated: list[TreasureMatrixEntry]


def _load_profiles_from_file(path: Path) -> ProfileCollection | None:
    """从 JSON 文件加载账号配置。"""
    if not path.exists():
        return None
    if not path.is_file():
        raise ProfileLoadError(f"账号配置路径不是文件: {path}")

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return ProfileCollection.model_validate(obj)
    except (OSError, JSONDecodeError, ValidationError) as exc:
        broken_path = path.with_suffix(f"{path.suffix}.broken")
        try:
            if broken_path.exists():
                broken_path = path.with_suffix(f"{path.suffix}.broken.{os.getpid()}")
            path.replace(broken_path)
            logger.error("账号配置文件无效，已备份到: {}", broken_path)
        except OSError:
            logger.exception("账号配置文件无效，且备份失败: {}", path)
        raise ProfileLoadError(f"账号配置文件无法加载: {path}") from exc


def _save_profiles_to_file(collection: ProfileCollection, path: Path) -> None:
    """原子性地保存账号配置到 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = collection.model_dump_json(indent=4, ensure_ascii=False)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    tmp_path = type(path)(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())

        os.replace(tmp_path, path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("清理账号配置临时文件失败: {}", tmp_path)
        logger.exception("保存账号配置失败: {}", path)
        raise ProfileSaveError(f"账号配置文件无法保存: {path}") from exc


class ProfileManager:
    """
    管理多账号。

    - 在内存中保存 ProfileCollection。
    - 提供账号的 CRUD 操作。
    - 在更改时持久化到磁盘。
    """

    def __init__(self, profiles_file: Path) -> None:
        """初始化账号管理器。

        Args:
            profiles_file: 账号持久化的 JSON 文件路径。
        """
        self._profiles_file = profiles_file
        self._collection = ProfileCollection()
        self._lock = threading.RLock()

    def load(self) -> None:
        """从磁盘加载账号配置。"""
        with self._lock:
            result = _load_profiles_from_file(self._profiles_file)
            if result is not None:
                self._collection = result
                self._heal_default_profile_unlocked()
                self._collection.ensure_default()
                logger.info(
                    "加载账号配置成功，当前账号: {}", self._collection.active_profile
                )
            else:
                logger.info("未找到账号配置文件，使用默认配置。")
                collection = ProfileCollection()
                collection.ensure_default()
                _save_profiles_to_file(collection, self._profiles_file)
                self._collection = collection

    def _heal_default_profile_unlocked(self) -> None:
        """修正指向不存在账号的 default_profile；调用方必须已经持有 `_lock`。

        优先复用现有的 'default' 账号，避免凭空造出一个既没有数据、
        又因保留名校验而无法切换过去的僵尸账号。
        """
        collection = self._collection
        if collection.default_profile in collection.profiles:
            return

        if DEFAULT_PROFILE_NAME in collection.profiles:
            logger.warning(
                "默认账号 '{}' 在配置文件中不存在，已回退到 '{}'",
                collection.default_profile,
                DEFAULT_PROFILE_NAME,
            )
            collection.default_profile = DEFAULT_PROFILE_NAME
        else:
            logger.warning(
                "默认账号 '{}' 在配置文件中不存在且没有 '{}' 账号，已回退到 '{}'",
                collection.default_profile,
                DEFAULT_PROFILE_NAME,
                DEFAULT_PROFILE_NAME,
            )
            collection.default_profile = DEFAULT_PROFILE_NAME

    def save(self) -> None:
        """保存账号配置到磁盘。"""
        with self._lock:
            self._save_unlocked()

    def migrate_custom_stat_ids(self, custom_stat_ids: list[str]) -> bool:
        """把旧格式 `custom_stat_{index}` 引用改写为稳定的 `custom:{id}`。

        下标越界的引用（配置中已被删掉、但 profile 里还留着的孤儿条目）会被
        丢弃——它们本来就指不到任何自定义基质，保留只会在界面上显示成幽灵条目。

        已知局限：v7 时代删除过自定义基质且未清理 profile 引用的配置，
        残留的旧下标会因列表前移而错绑到相邻条目（无法从数据上区分）。
        该迁移为一次性操作，错绑仅在升级瞬间发生且影响有限。

        幂等：已是新格式的引用不受影响，可安全地在每次启动时调用。

        Args:
            custom_stat_ids: 按配置顺序排列的稳定 ID，下标即旧编号。

        Returns:
            是否发生了改写（调用方据此决定是否需要写盘）。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            changed = False
            dropped = 0

            def resolve(weapon_id: str) -> str | None:
                """返回新 ID；None 表示该引用已失效、应当丢弃。"""
                if not weapon_id.startswith(LEGACY_CUSTOM_ID_PREFIX):
                    return weapon_id
                raw = weapon_id[len(LEGACY_CUSTOM_ID_PREFIX) :]
                if not raw.isdigit():
                    return None
                index = int(raw)
                if index >= len(custom_stat_ids):
                    return None
                return f"{CUSTOM_ID_PREFIX}{custom_stat_ids[index]}"

            for profile in collection.profiles.values():
                new_matrix = []
                for entry in profile.treasure_matrix:
                    resolved = resolve(entry.weapon_id)
                    if resolved is None:
                        dropped += 1
                        changed = True
                        continue
                    if resolved != entry.weapon_id:
                        entry.weapon_id = resolved
                        changed = True
                    new_matrix.append(entry)
                profile.treasure_matrix = new_matrix

                new_priorities: dict[str, int] = {}
                for weapon_id, priority in profile.weapon_priorities.items():
                    resolved = resolve(weapon_id)
                    if resolved is None:
                        changed = True
                        continue
                    if resolved != weapon_id:
                        changed = True
                    new_priorities[resolved] = priority
                profile.weapon_priorities = new_priorities

            if changed:
                self._commit_collection_unlocked(collection)
                logger.info(
                    "已将自定义基质引用迁移为稳定 ID{}",
                    f"，丢弃 {dropped} 条失效引用" if dropped else "",
                )
            return changed

    def migrate_stale_weapon_ids(self, weapons_by_name: dict[str, str]) -> bool:
        """把因武器 ID 变更而失效的内置武器引用改写为最新 ID。

        武器数据随游戏版本更新后，个别武器的 `weapon_id` 可能变化（例如把
        中文 ID 规范为 `wpn_xxx`）。profile 里以旧 ID 保存的引用在新数据中
        查不到，会导致宝藏基质页条目被静默过滤、武器总览误判未拥有、扫描
        在旧引用旁新增重复条目。

        这里按武器名称把旧 ID 改写为新 ID——名称是条目里唯一稳定的标识：
        先用缓存的 `weapon_name` 匹配，为空时退化为用旧 ID 本身当名称匹配
        （旧中文 ID 通常就是武器名称）。匹配不到的名称保持原样，绝不丢弃
        用户数据。自定义基质引用由 `migrate_custom_stat_ids` 处理，不在此列。

        幂等：已是新 ID 的引用不受影响，可安全地在每次启动时调用。

        Args:
            weapons_by_name: 武器名称 -> 最新 weapon_id 的映射。

        Returns:
            是否发生了改写（调用方据此决定是否需要写盘）。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            changed = False
            valid_ids = set(weapons_by_name.values())

            def resolve(weapon_id: str, weapon_name: str) -> str:
                """返回该引用的最新 ID；无法确定时原样返回。"""
                if (
                    weapon_id in valid_ids
                    or weapon_id.startswith(CUSTOM_ID_PREFIX)
                    or weapon_id.startswith(LEGACY_CUSTOM_ID_PREFIX)
                ):
                    return weapon_id
                candidate = weapon_name or weapon_id
                return weapons_by_name.get(candidate, weapon_id)

            for profile in collection.profiles.values():
                for entry in profile.treasure_matrix:
                    resolved = resolve(entry.weapon_id, entry.weapon_name)
                    if resolved != entry.weapon_id:
                        entry.weapon_id = resolved
                        changed = True

                new_priorities: dict[str, int] = {}
                for weapon_id, priority in profile.weapon_priorities.items():
                    resolved = resolve(weapon_id, "")
                    if resolved != weapon_id:
                        changed = True
                    new_priorities[resolved] = priority
                profile.weapon_priorities = new_priorities

            if changed:
                self._commit_collection_unlocked(collection)
                logger.info("已将失效的内置武器引用迁移为最新 ID")
            return changed

    def prune_custom_stat_refs(self, valid_ids: set[str]) -> bool:
        """移除所有账号中指向已不存在自定义基质的引用。

        自定义基质被删除后，各账号的矩阵与优先级里仍残留 `custom:{id}` 引用。
        这类引用查不到属性来源，在界面上表现为属性未知、不参与任何判定的幽灵
        条目；而稳定 ID 是一次性 UUID，重新添加相同属性组合只会生成新 ID，
        旧引用永远无法复活，因此没有保留价值。

        旧格式 `custom_stat_{下标}` 一律视为失效：启动时的
        `migrate_custom_stat_ids` 已把可解析的引用改写成新格式，运行期还能
        遇到的必然是当时就解析不出的孤儿。

        Args:
            valid_ids: 当前配置中存活的自定义基质稳定 ID（不含 `custom:` 前缀）。
                传入空集合表示配置里一条自定义基质都不剩，即清除全部引用。

        Returns:
            是否发生了变更（调用方据此决定是否需要写盘）。
        """
        with self._lock:
            live_refs = {f"{CUSTOM_ID_PREFIX}{stat_id}" for stat_id in valid_ids}

            def is_orphan(weapon_id: str) -> bool:
                """该引用指向自定义基质，但在当前配置中已找不到对应条目。"""
                if weapon_id.startswith(LEGACY_CUSTOM_ID_PREFIX):
                    return True
                return (
                    weapon_id.startswith(CUSTOM_ID_PREFIX)
                    and weapon_id not in live_refs
                )

            def has_orphan(profile: ProfileData) -> bool:
                return any(
                    is_orphan(entry.weapon_id) for entry in profile.treasure_matrix
                ) or any(
                    is_orphan(weapon_id) for weapon_id in profile.weapon_priorities
                )

            # 先只读探测：设置页每次改动都会保存一次配置，无谓的深拷贝会被放大。
            if not any(has_orphan(p) for p in self._collection.profiles.values()):
                return False

            collection = self._collection.model_copy(deep=True)
            dropped_entries = 0
            dropped_priorities = 0
            for profile in collection.profiles.values():
                kept_matrix = [
                    entry
                    for entry in profile.treasure_matrix
                    if not is_orphan(entry.weapon_id)
                ]
                dropped_entries += len(profile.treasure_matrix) - len(kept_matrix)
                profile.treasure_matrix = kept_matrix

                kept_priorities = {
                    weapon_id: priority
                    for weapon_id, priority in profile.weapon_priorities.items()
                    if not is_orphan(weapon_id)
                }
                dropped_priorities += len(profile.weapon_priorities) - len(
                    kept_priorities
                )
                profile.weapon_priorities = kept_priorities

            self._commit_collection_unlocked(collection)
            logger.info(
                "已清理指向已删除自定义基质的引用：{} 条宝藏基质条目、{} 个优先级键",
                dropped_entries,
                dropped_priorities,
            )
            return True

    def _save_unlocked(self) -> None:
        """保存账号配置；调用方必须已经持有 `_lock`。"""
        _save_profiles_to_file(self._collection, self._profiles_file)

    def _commit_collection_unlocked(self, collection: ProfileCollection) -> None:
        """保存新集合并在成功后替换内存状态；调用方必须已经持有 `_lock`。"""
        _save_profiles_to_file(collection, self._profiles_file)
        self._collection = collection

    def _get_active_unlocked(self) -> ProfileData:
        """获取激活账号；调用方必须已经持有 `_lock`。"""
        return self._collection.get_active()

    def _update_active_profile_unlocked(
        self,
        mutator: Callable[[ProfileData], None],
        *,
        name: str | None = None,
    ) -> ProfileData:
        """更新账号数据并提交到磁盘；调用方必须已经持有 `_lock`。

        这是一个辅助方法，用于简化常见的 lock-copy-modify-commit 模式。

        Args:
            mutator: 一个函数，接收 ProfileData 并就地修改它。
            name: 要更新的账号名称；None 表示更新当前激活账号。

        Returns:
            更新后的 ProfileData 的深拷贝。

        Raises:
            ValueError: 如果指定的账号不存在。
        """
        collection = self._collection.model_copy(deep=True)
        if name is None:
            profile = collection.get_active()
        elif name in collection.profiles:
            profile = collection.profiles[name]
        else:
            raise ValueError(f"账号 '{name}' 不存在")
        mutator(profile)
        self._commit_collection_unlocked(collection)
        return profile.model_copy(deep=True)

    @staticmethod
    def _sync_priority_projection(profile: ProfileData) -> None:
        """以 weapon_priorities 为准回填矩阵条目的 priority。

        优先级有唯一权威来源 `weapon_priorities`——只有它能表达"未拥有基质
        但用户设过优先级"；`entry.priority` 只是给前端就近读取的投影。
        所有写路径改完权威源后统一调用本方法收敛，避免各处各写一遍同步
        逻辑，日久必然漂移。
        """
        for entry in profile.treasure_matrix:
            entry.priority = profile.weapon_priorities.get(entry.weapon_id, 0)

    def get_collection(self) -> ProfileCollection:
        """获取当前账号集合。"""
        with self._lock:
            return self._collection.model_copy(deep=True)

    def get_active_profile(self) -> ProfileData:
        """获取激活的账号数据。"""
        with self._lock:
            return self._get_active_unlocked().model_copy(deep=True)

    def get_active_profile_name(self) -> str:
        """获取激活的账号名称。"""
        with self._lock:
            return self._collection.active_profile

    def switch_profile(self, name: str) -> ProfileData:
        """切换到指定账号，如果不存在则创建。

        Args:
            name: 要切换到的账号名称。必须在去除空白后非空，
                最多 32 个字符，且不能包含路径分隔符或换行符。

        Returns:
            切换到的账号的 ProfileData。

        Raises:
            ValueError: 如果名称无效。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            name = self._validate_profile_name(name)
            # 仅拦截"新建"保留名账号；已存在的同名账号允许切换过去，
            # 避免历史数据把用户困在无法访问的账号上。
            if (
                name == DEFAULT_PROFILE_NAME
                and collection.default_profile != DEFAULT_PROFILE_NAME
                and name not in collection.profiles
            ):
                raise ValueError(
                    f"不能使用保留名称 '{DEFAULT_PROFILE_NAME}' 作为账号名称"
                )
            if name not in collection.profiles:
                collection.profiles[name] = ProfileData(name=name)
            collection.active_profile = name
            self._commit_collection_unlocked(collection)
            logger.info("切换到账号: {}", name)
            return collection.profiles[name].model_copy(deep=True)

    @staticmethod
    def _validate_profile_name(name: str) -> str:
        """验证并规范化账号名称。

        规则：
        - 去除空白后非空
        - 最多 32 个字符
        - 不能包含路径分隔符、换行符或空字节

        Args:
            name: 原始账号名称。

        Returns:
            去除空白后的账号名称。

        Raises:
            ValueError: 如果名称违反任何规则。
        """
        stripped = name.strip()
        if not stripped:
            raise ValueError("账号名称不能为空")
        if len(stripped) > 32:
            raise ValueError("账号名称不能超过 32 个字符")
        forbidden = {
            "/": "正斜杠(/)",
            "\\": "反斜杠(\\)",
            "\x00": "空字节",
            "\n": "换行符",
            "\r": "回车符",
            "\t": "制表符",
        }
        bad_chars = [forbidden[c] for c in stripped if c in forbidden]
        if bad_chars:
            raise ValueError(f"账号名称包含非法字符: {', '.join(sorted(bad_chars))}")
        return stripped

    def rename_profile(self, old_name: str, new_name: str) -> ProfileData:
        """重命名账号（含默认账号）。

        Args:
            old_name: 当前账号名称。必须存在。
            new_name: 新账号名称。必须有效且未被使用。

        Returns:
            重命名后的 ProfileData。

        Raises:
            ValueError: 如果 old_name 不存在、new_name 已被占用或 new_name 无效。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            if old_name not in collection.profiles:
                raise ValueError(f"账号 '{old_name}' 不存在")
            new_name = self._validate_profile_name(new_name)
            if new_name == old_name:
                # 同名重命名视为无操作，避免把"未修改"误报为名称冲突。
                return collection.profiles[old_name].model_copy(deep=True)
            # 默认账号本身改回 'default' 是允许的（这正是撤销改名的唯一途径）；
            # 只有其它账号才禁止占用该保留名。
            if (
                new_name == DEFAULT_PROFILE_NAME
                and collection.default_profile != DEFAULT_PROFILE_NAME
                and collection.default_profile != old_name
            ):
                raise ValueError(
                    f"不能使用保留名称 '{DEFAULT_PROFILE_NAME}' 作为账号名称"
                )
            if new_name in collection.profiles:
                raise ValueError(f"账号 '{new_name}' 已存在")

            profile = collection.profiles.pop(old_name)
            profile.name = new_name
            collection.profiles[new_name] = profile

            if collection.active_profile == old_name:
                collection.active_profile = new_name
            if collection.default_profile == old_name:
                collection.default_profile = new_name

            self._commit_collection_unlocked(collection)
            logger.info("重命名账号: {} -> {}", old_name, new_name)
            return profile.model_copy(deep=True)

    def delete_profile(self, name: str) -> None:
        """删除账号。

        不能删除默认账号；删除当前激活的账号后会自动切换回默认账号。

        Args:
            name: 要删除的账号名称。

        Raises:
            ValueError: 如果账号是默认账号或不存在。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            if name == collection.default_profile:
                raise ValueError("不能删除默认账号")
            if name not in collection.profiles:
                raise ValueError(f"账号 '{name}' 不存在")

            del collection.profiles[name]
            if collection.active_profile == name:
                collection.active_profile = collection.default_profile
                logger.info(
                    "删除激活账号: {}，已自动切换回默认账号: {}",
                    name,
                    collection.default_profile,
                )
            self._commit_collection_unlocked(collection)
            logger.info("删除账号: {}", name)

    def update_treasure_matrix(self, entries: list[TreasureMatrixEntry]) -> ProfileData:
        """替换激活账号的完整宝藏基质配置。

        矩阵内条目的优先级以 entry.priority 为准同步进 weapon_priorities；
        未出现在矩阵中的武器（未拥有基质但用户设过优先级）保持原值不变，
        详见 `update_weapon_priority` 的契约。

        Args:
            entries: 新的宝藏基质条目列表。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            profile.treasure_matrix = [entry.model_copy(deep=True) for entry in entries]

            matrix_ids = {entry.weapon_id for entry in profile.treasure_matrix}
            # 先保留未拥有武器的优先级，再用矩阵内条目的 priority 覆盖同名键。
            merged = {
                weapon_id: priority
                for weapon_id, priority in profile.weapon_priorities.items()
                if weapon_id not in matrix_ids
            }
            merged.update(
                {
                    entry.weapon_id: entry.priority
                    for entry in profile.treasure_matrix
                    if entry.priority > 0
                }
            )
            profile.weapon_priorities = merged
            self._sync_priority_projection(profile)
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)

    def add_treasure_matrix_entry(self, entry: TreasureMatrixEntry) -> ProfileData:
        """添加或更新单个宝藏基质条目。

        如果相同 weapon_id 的条目已存在，则替换它。

        Args:
            entry: 要添加或更新的宝藏基质条目。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            entry = entry.model_copy(deep=True)
            if entry.priority > 0 and entry.weapon_id not in profile.weapon_priorities:
                profile.weapon_priorities[entry.weapon_id] = entry.priority
            profile.treasure_matrix = [
                e for e in profile.treasure_matrix if e.weapon_id != entry.weapon_id
            ]
            profile.treasure_matrix.append(entry)
            self._sync_priority_projection(profile)
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)

    def sync_treasure_matrix_entries(
        self, entries: list[TreasureMatrixEntry]
    ) -> TreasureMatrixSyncResult:
        """批量同步扫描得到的宝藏基质条目，并且最多只保存一次。

        扫描通常一次返回多把武器。逐个调用 `add_treasure_matrix_entry()` 会
        对同一个 JSON 文件重复序列化和写盘；这里先在内存中完成所有合并，最后
        在确实有变更时统一保存。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            existing_by_weapon_id = {
                entry.weapon_id: entry for entry in profile.treasure_matrix
            }
            added: list[TreasureMatrixEntry] = []
            updated: list[TreasureMatrixEntry] = []

            for incoming in entries:
                incoming = incoming.model_copy(deep=True)
                existing = existing_by_weapon_id.get(incoming.weapon_id)
                if existing is None:
                    # 已有的手动优先级优先于扫描结果携带的值
                    if (
                        incoming.priority > 0
                        and incoming.weapon_id not in profile.weapon_priorities
                    ):
                        profile.weapon_priorities[incoming.weapon_id] = (
                            incoming.priority
                        )

                    profile.treasure_matrix.append(incoming)
                    existing_by_weapon_id[incoming.weapon_id] = incoming
                    added.append(incoming)
                    continue

                level_changed = False
                if existing.affix1_level < incoming.affix1_level:
                    existing.affix1_level = incoming.affix1_level
                    level_changed = True
                if existing.affix2_level < incoming.affix2_level:
                    existing.affix2_level = incoming.affix2_level
                    level_changed = True
                if existing.affix3_level < incoming.affix3_level:
                    existing.affix3_level = incoming.affix3_level
                    level_changed = True

                # 只在扫描到更高等级时自动关闭满级武器，避免无变更扫描覆盖用户选择。
                if level_changed and (
                    existing.affix1_level == AFFIX1_MAX_LEVEL
                    and existing.affix2_level == AFFIX2_MAX_LEVEL
                    and existing.affix3_level == AFFIX3_MAX_LEVEL
                ):
                    existing.include_in_calculation = False

                if level_changed:
                    updated.append(existing)

            if added or updated:
                self._sync_priority_projection(profile)
                self._commit_collection_unlocked(collection)

            return TreasureMatrixSyncResult(
                profile=profile.model_copy(deep=True),
                added=[entry.model_copy(deep=True) for entry in added],
                updated=[entry.model_copy(deep=True) for entry in updated],
            )

    def remove_treasure_matrix_entry(self, weapon_id: str) -> ProfileData:
        """根据武器 ID 移除宝藏基质条目。

        Args:
            weapon_id: 要移除的条目的武器 ID。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            profile.treasure_matrix = [
                e for e in profile.treasure_matrix if e.weapon_id != weapon_id
            ]
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)

    def clear_profile_data(self, name: str | None = None) -> ProfileData:
        """清空指定账号的宝藏基质数据（保留账号本身、名称、版本与展示偏好）。

        清空内容为 treasure_matrix 与 weapon_priorities，用于「数据有误、
        全量重新扫描」的场景；不删除账号，也不重置武器总览过滤器、
        刷取地点筛选等展示偏好。

        Args:
            name: 要清空的账号名称；None 表示清空当前激活账号。

        Returns:
            清空后的 ProfileData。

        Raises:
            ValueError: 如果指定的账号不存在。
        """
        with self._lock:

            def _mutator(profile: ProfileData) -> None:
                profile.treasure_matrix = []
                profile.weapon_priorities = {}

            result = self._update_active_profile_unlocked(_mutator, name=name)
            logger.info("清空账号数据: {}", result.name)
            return result

    def fix_weapon_id(self, old_weapon_id: str, new_weapon_id: str) -> None:
        """修正 profile 中错误的武器 ID（如名称 → 正确 ID）。

        同时迁移 weapon_priorities 中的对应条目。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            changed = False
            for entry in profile.treasure_matrix:
                if entry.weapon_id == old_weapon_id:
                    entry.weapon_id = new_weapon_id
                    changed = True
            if old_weapon_id in profile.weapon_priorities:
                profile.weapon_priorities[new_weapon_id] = (
                    profile.weapon_priorities.pop(old_weapon_id)
                )
                changed = True
            if changed:
                self._commit_collection_unlocked(collection)

    def update_weapon_overview_filters(self, filters: dict[str, bool]) -> ProfileData:
        """更新激活账号的武器总览过滤器配置。

        Args:
            filters: 星级过滤器配置字典。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            profile.weapon_overview_filters = filters
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)

    def update_matrix_planner_farming_locations(
        self, locations: dict[str, bool]
    ) -> ProfileData:
        """更新激活账号的基质规划刷取地点筛选配置。

        Args:
            locations: 刷取地点筛选配置字典（battleId -> 是否勾选）。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            profile.matrix_planner_farming_locations = locations
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)

    def update_switch_display_mode(self, mode: str) -> ProfileData:
        """更新激活账号的"可切换"提示显示模式。

        Args:
            mode: 显示模式，'chip' | 'dot' | 'off'。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:

            def _mutator(profile: ProfileData) -> None:
                profile.switch_display_mode = mode

            return self._update_active_profile_unlocked(_mutator)

    def update_matrix_badge_display_mode(self, mode: str) -> ProfileData:
        """更新激活账号的基质图标显示模式。

        Args:
            mode: 显示模式，'small' | 'medium' | 'off'。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:

            def _mutator(profile: ProfileData) -> None:
                profile.matrix_badge_display_mode = mode

            return self._update_active_profile_unlocked(_mutator)

    def update_weapon_priority(self, weapon_id: str, priority: int) -> ProfileData:
        """更新单个武器优先级，未拥有宝藏基质的武器也会保存。

        Args:
            weapon_id: 武器 ID。
            priority: 优先级。0 表示清除手动设置并回到稀有度默认值。

        Returns:
            更新后的 ProfileData。
        """
        with self._lock:
            collection = self._collection.model_copy(deep=True)
            profile = collection.get_active()
            if priority > 0:
                profile.weapon_priorities[weapon_id] = priority
            else:
                profile.weapon_priorities.pop(weapon_id, None)

            self._sync_priority_projection(profile)
            self._commit_collection_unlocked(collection)
            return profile.model_copy(deep=True)
