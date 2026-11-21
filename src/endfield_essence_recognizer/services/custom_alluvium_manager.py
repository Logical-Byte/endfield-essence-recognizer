"""自定义能量淤积点的持久化服务。

数据落盘在程序根目录的 `custom_alluviums.json`，文件内容就是
`CustomAlluvium` 列表。该文件与账号数据解耦：全账号通用，不属于任何一个
`profiles.json` 里的账号。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from json import JSONDecodeError
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from endfield_essence_recognizer.schemas.custom_alluvium import CustomAlluvium
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["CustomAlluviumManager", "CustomAlluviumReadError"]

# FastAPI 的同步路由跑在线程池里，跨请求的「读-改-写」可能交错；
# 管理器本身无内存状态，用模块级锁把同一文件的读改写串起来。
_FILE_LOCK = threading.Lock()

_ALLUVIUMS_TYPE_ADAPTER: TypeAdapter[list[CustomAlluvium]] = TypeAdapter(
    list[CustomAlluvium]
)


class CustomAlluviumReadError(RuntimeError):
    """数据文件存在但读不出来（权限、占用等）。

    这类错误不能当成「文件为空」处理：调用方随后一次保存会把读不出来的条目
    整体覆盖掉，等于丢掉用户已经保存的自定义地点。因此既不做 `.broken` 备份
    （文件本身是好的，只是这次读不到），也不返回空列表。
    """


def _backup_broken_file(path: Path) -> None:
    """把无法解析的文件改名保留，避免随后一次保存把它直接覆盖掉。"""
    broken_path = path.with_suffix(f"{path.suffix}.broken")
    try:
        if broken_path.exists():
            broken_path = path.with_suffix(f"{path.suffix}.broken.{os.getpid()}")
        path.replace(broken_path)
        logger.error("自定义淤积点文件无效，已备份到: {}", broken_path)
    except OSError:
        logger.exception("自定义淤积点文件无效，且备份失败: {}", path)


class CustomAlluviumManager:
    """读写 `custom_alluviums.json`。

    无内存状态：每次操作都直接读文件，因此可以按请求构造，不需要在应用
    启动时初始化。自定义淤积点数量很少（个位数），这点 IO 可以忽略。
    """

    def __init__(self, data_file: Path) -> None:
        """初始化管理器。

        Args:
            data_file: 自定义淤积点持久化的 JSON 文件路径。
        """
        self._data_file = data_file

    def list_all(self) -> list[CustomAlluvium]:
        """返回全部自定义淤积点。

        Returns:
            按文件顺序排列的条目；文件不存在时返回空列表。

        Raises:
            CustomAlluviumReadError: 文件存在但读取失败。
        """
        with _FILE_LOCK:
            alluviums, healed = self._read_unlocked()
            if healed:
                # 补齐的 ID 必须落盘：前端拿到的 ID 是后续编辑/删除的唯一钥匙，
                # 只在内存里随机生成会让下一次请求删不到这一条。
                try:
                    self._write_unlocked(alluviums)
                except OSError:
                    # 目录只读等情况下列表仍应可用，ID 会在下一次成功写入时固定下来
                    logger.warning("补齐自定义淤积点 ID 后写盘失败，ID 暂不稳定")
            return alluviums

    def upsert(self, entry: CustomAlluvium) -> list[CustomAlluvium]:
        """按稳定 ID 新增或覆盖一条自定义淤积点。

        Args:
            entry: 待保存的条目；`id` 为空表示新建。

        Returns:
            保存后的完整列表。

        Raises:
            ValueError: 名称为空。
            CustomAlluviumReadError: 文件存在但读取失败（此时不会覆盖原文件）。
        """
        name = entry.name.strip()
        if not name:
            raise ValueError("自定义淤积点名称不能为空")

        with _FILE_LOCK:
            alluviums, _ = self._read_unlocked()
            normalized = entry.model_copy(
                update={"id": entry.id or uuid4().hex, "name": name}
            )
            for index, existing in enumerate(alluviums):
                if existing.id == normalized.id:
                    alluviums[index] = normalized
                    break
            else:
                alluviums.append(normalized)
            self._write_unlocked(alluviums)
            return alluviums

    def delete(self, alluvium_id: str) -> list[CustomAlluvium]:
        """按稳定 ID 删除一条自定义淤积点。

        Args:
            alluvium_id: 目标条目的稳定 ID；不存在时什么也不做（幂等）。

        Returns:
            删除后的完整列表。

        Raises:
            CustomAlluviumReadError: 文件存在但读取失败。
        """
        with _FILE_LOCK:
            alluviums, healed = self._read_unlocked()
            kept = [item for item in alluviums if item.id != alluvium_id]
            if len(kept) != len(alluviums) or healed:
                self._write_unlocked(kept)
            return kept

    def _read_unlocked(self) -> tuple[list[CustomAlluvium], bool]:
        """读取并校验文件；调用方必须已经持有 `_FILE_LOCK`。

        Returns:
            (条目列表, 是否发生了 ID 补齐)。文件缺失或内容无效时返回空列表，
            后者会先把原文件备份成 `.broken`。

        Raises:
            CustomAlluviumReadError: 文件存在但读取失败（权限、被占用等）。
        """
        if not self._data_file.is_file():
            return [], False

        try:
            text = self._data_file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            # 非法 UTF-8 与 JSON 语法错误同属内容损坏，按损坏处理并备份
            logger.error("自定义淤积点文件编码无效: {}", exc)
            _backup_broken_file(self._data_file)
            return [], False
        except OSError as exc:
            raise CustomAlluviumReadError(
                f"读取自定义淤积点文件失败: {self._data_file}"
            ) from exc

        try:
            raw = json.loads(text)
            alluviums = _ALLUVIUMS_TYPE_ADAPTER.validate_python(raw)
        except (JSONDecodeError, ValidationError) as exc:
            logger.error("加载自定义淤积点失败: {}", exc)
            _backup_broken_file(self._data_file)
            return [], False

        return alluviums, _ensure_ids(alluviums)

    def _write_unlocked(self, alluviums: list[CustomAlluvium]) -> None:
        """原子性地写入文件；调用方必须已经持有 `_FILE_LOCK`。

        先写临时文件再 rename，避免写入中断后留下半截 JSON（那样下次读取会
        判定文件损坏并备份，等于丢掉全部自定义淤积点）。
        """
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        data = _ALLUVIUMS_TYPE_ADAPTER.dump_json(
            alluviums, indent=4, ensure_ascii=False
        ).decode("utf-8")

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self._data_file.name}.",
            suffix=".tmp",
            dir=self._data_file.parent,
            text=True,
        )
        tmp_path = type(self._data_file)(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, self._data_file)
        except OSError:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("清理自定义淤积点临时文件失败: {}", tmp_path)
            logger.exception("保存自定义淤积点失败: {}", self._data_file)
            raise


def _ensure_ids(alluviums: list[CustomAlluvium]) -> bool:
    """为缺失或重复的稳定 ID 重新分配（就地修改）。

    手工编辑配置时很容易漏掉 ID；重复 ID 会让按 ID 的覆盖与删除打到错误的
    条目上，因此两者都在读取时修掉。

    Returns:
        是否发生了变更（调用方据此决定是否需要写回磁盘）。
    """
    changed = False
    seen: set[str] = set()
    for item in alluviums:
        if not item.id or item.id in seen:
            item.id = uuid4().hex
            changed = True
        seen.add(item.id)
    return changed
