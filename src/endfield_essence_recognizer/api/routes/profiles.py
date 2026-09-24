"""
账号管理 API 路由。

提供管理多账号配置及其宝藏基质配置的接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from endfield_essence_recognizer.core.farming_calculator import (
    FarmingRecommendation,
    compute_farming_recommendation,
)
from endfield_essence_recognizer.dependencies import get_static_game_data
from endfield_essence_recognizer.schemas.profile import (
    CUSTOM_ID_PREFIX,
    LEGACY_CUSTOM_ID_PREFIX,
    ProfileCollection,
    ProfileData,
    TreasureMatrixEntry,
)

if TYPE_CHECKING:
    from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
    from endfield_essence_recognizer.services.profile_manager import ProfileManager

router = APIRouter(prefix="/profiles", tags=["profiles"])

# 全局账号管理器实例（在应用启动时设置）
_profile_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """获取全局账号管理器实例。"""
    if _profile_manager is None:
        raise HTTPException(status_code=503, detail="Profile manager not initialized")
    return _profile_manager


def set_profile_manager(manager: ProfileManager) -> None:
    """设置全局账号管理器实例。"""
    global _profile_manager
    _profile_manager = manager


def _is_custom_stat_id(weapon_id: str) -> bool:
    """判断 weapon_id 是否指向自定义基质（兼容迁移前的旧格式）。"""
    return weapon_id.startswith(CUSTOM_ID_PREFIX) or weapon_id.startswith(
        LEGACY_CUSTOM_ID_PREFIX
    )


# --- 账号 CRUD ---


@router.get("")
async def list_profiles(
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileCollection:
    """获取所有账号及当前激活的账号名称。"""
    return manager.get_collection()


@router.get("/active")
async def get_active_profile(
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """获取当前激活的账号数据。"""
    return manager.get_active_profile()


class SwitchProfileRequest(BaseModel):
    """切换账号请求体。"""

    name: str


@router.post("/switch")
async def switch_profile(
    request: SwitchProfileRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """切换到不同的账号。"""
    try:
        return manager.switch_profile(request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class RenameProfileRequest(BaseModel):
    """重命名账号请求体。"""

    old_name: str
    new_name: str


@router.post("/rename")
async def rename_profile(
    request: RenameProfileRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """重命名账号。"""
    try:
        return manager.rename_profile(request.old_name, request.new_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class DeleteProfileRequest(BaseModel):
    """删除账号请求体。"""

    name: str


@router.post("/delete")
async def delete_profile(
    request: DeleteProfileRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> dict[str, str]:
    """删除账号。"""
    try:
        manager.delete_profile(request.name)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class ClearProfileDataRequest(BaseModel):
    """清空账号数据请求体。"""

    name: str | None = None


@router.post("/clear_data")
async def clear_profile_data(
    request: ClearProfileDataRequest | None = None,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """清空账号的宝藏基质数据（不删除账号）。

    name 为空时清空当前激活账号的数据。
    """
    try:
        return manager.clear_profile_data(request.name if request else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- 宝藏基质 ---


@router.get("/treasure_matrix")
async def get_treasure_matrix(
    manager: ProfileManager = Depends(get_profile_manager),
) -> list[TreasureMatrixEntry]:
    """获取当前激活账号的宝藏基质配置。"""
    return manager.get_active_profile().treasure_matrix


class UpdateTreasureMatrixRequest(BaseModel):
    """更新完整宝藏基质配置的请求体。"""

    entries: list[TreasureMatrixEntry]


@router.post("/treasure_matrix")
async def update_treasure_matrix(
    request: UpdateTreasureMatrixRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的完整宝藏基质配置。"""
    return manager.update_treasure_matrix(request.entries)


class AddTreasureMatrixEntryRequest(BaseModel):
    """新增或更新单个宝藏基质条目的请求体。"""

    weapon_id: str
    weapon_name: str = ""
    affix1_level: int = Field(default=1, ge=1, le=6)
    affix2_level: int = Field(default=1, ge=1, le=6)
    affix3_level: int = Field(default=1, ge=1, le=3)
    include_in_calculation: bool = True


@router.post("/treasure_matrix/add")
async def add_treasure_matrix_entry(
    request: AddTreasureMatrixEntryRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """添加或更新单个宝藏基质条目。"""
    entry = TreasureMatrixEntry(
        weapon_id=request.weapon_id,
        weapon_name=request.weapon_name,
        affix1_level=request.affix1_level,
        affix2_level=request.affix2_level,
        affix3_level=request.affix3_level,
        include_in_calculation=request.include_in_calculation,
    )
    return manager.add_treasure_matrix_entry(entry)


class RemoveTreasureMatrixEntryRequest(BaseModel):
    """移除单个宝藏基质条目的请求体。"""

    weapon_id: str


@router.post("/treasure_matrix/remove")
async def remove_treasure_matrix_entry(
    request: RemoveTreasureMatrixEntryRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """移除宝藏基质条目。"""
    return manager.remove_treasure_matrix_entry(request.weapon_id)


# --- 刷取建议 ---


class FarmingRequest(BaseModel):
    """计算单把武器刷取建议的请求体。"""

    weapon_id: str
    current_levels: tuple[int, int, int] = Field(
        default=(1, 1, 1),
        description="当前词条等级 (基础属性1-6, 附加属性1-6, 技能属性1-3)",
    )
    target_levels: tuple[int, int, int] = Field(
        default=(6, 6, 3),
        description="目标词条等级 (基础属性1-6, 附加属性1-6, 技能属性1-3)",
    )


@router.post("/farming_recommendation")
async def get_farming_recommendation(
    request: FarmingRequest,
    static_data: StaticGameData = Depends(get_static_game_data),
) -> FarmingRecommendation:
    """计算武器宝藏基质的刷取建议。"""
    weapon = static_data.get_weapon(request.weapon_id)
    if not weapon:
        raise HTTPException(status_code=404, detail="Weapon not found")

    try:
        return compute_farming_recommendation(
            weapon_id=request.weapon_id,
            weapon_name=weapon.name,
            current_levels=request.current_levels,
            target_levels=request.target_levels,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class BatchFarmingRequest(BaseModel):
    """批量计算刷取建议的请求体。"""

    items: list[FarmingRequest] = Field(default_factory=list, max_length=100)


class BatchFarmingItemResult(BaseModel):
    """单个批量刷取建议的计算结果。"""

    weapon_id: str
    recommendation: FarmingRecommendation | None = None
    error: str | None = None


@router.post("/farming_recommendations")
async def get_batch_farming_recommendations(
    request: BatchFarmingRequest,
    static_data: StaticGameData = Depends(get_static_game_data),
) -> list[BatchFarmingItemResult]:
    """批量计算多个武器的刷取建议。"""
    results: list[BatchFarmingItemResult] = []
    for item in request.items:
        weapon = static_data.get_weapon(item.weapon_id)
        if weapon:
            weapon_name = weapon.name
        elif _is_custom_stat_id(item.weapon_id):
            weapon_name = item.weapon_id
        else:
            results.append(
                BatchFarmingItemResult(
                    weapon_id=item.weapon_id,
                    error="Weapon not found",
                )
            )
            continue

        try:
            recommendation = compute_farming_recommendation(
                weapon_id=item.weapon_id,
                weapon_name=weapon_name,
                current_levels=item.current_levels,
                target_levels=item.target_levels,
            )
            results.append(
                BatchFarmingItemResult(
                    weapon_id=item.weapon_id,
                    recommendation=recommendation,
                )
            )
        except ValueError as e:
            logger.warning("Invalid batch entry {}: {}", item.weapon_id, e)
            results.append(
                BatchFarmingItemResult(
                    weapon_id=item.weapon_id,
                    error=str(e),
                )
            )
    return results


# --- 等级比较 ---


class CompareLevelsItem(BaseModel):
    """单组等级比较请求。"""

    current_levels: tuple[int, int, int] = Field(
        description="当前基质的三个词条等级",
    )
    existing_levels: tuple[int, int, int] = Field(
        description="已保存基质的三个词条等级",
    )
    stat_types: list[str | None] = Field(
        default=["ATTRIBUTE", "SECONDARY", "SKILL"],
        min_length=3,
        max_length=3,
        description="各槽位的词条类型（ATTRIBUTE/SECONDARY/SKILL/null）",
    )

    @field_validator("stat_types")
    @classmethod
    def validate_stat_types(cls, value: list[str | None]) -> list[str | None]:
        """校验词条类型是否合法。"""
        valid_types = {"ATTRIBUTE", "SECONDARY", "SKILL", None}
        for i, stat_type in enumerate(value):
            if stat_type not in valid_types:
                raise ValueError(
                    f"未知词条类型: {stat_type}，槽位 {i} 可选: {[t for t in valid_types if t is not None]} 或 null"
                )
        return value


class CompareLevelsRequest(BaseModel):
    """批量等级比较请求体。"""

    items: list[CompareLevelsItem] = Field(max_length=100)
    mode: str = Field(
        default="sequential",
        description="比较模式：sequential/sum/grease/weighted_sum",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """校验比较模式是否合法。"""
        from endfield_essence_recognizer.schemas.user_setting import KeepBestMode

        try:
            KeepBestMode(value)
        except ValueError as err:
            raise ValueError(
                f"未知比较模式: {value}，可选: {[m.value for m in KeepBestMode]}"
            ) from err
        return value


class CompareLevelsResponse(BaseModel):
    """批量等级比较响应。"""

    results: list[int] = Field(
        description="每组的比较结果：1（当前更优）/ 0（相等）/ -1（当前更差）",
    )


@router.post("/compare_levels")
async def post_compare_levels(request: CompareLevelsRequest) -> CompareLevelsResponse:
    """批量比较等级，返回每组的比较结果。"""
    from endfield_essence_recognizer.core.scanner.evaluate import compare_levels
    from endfield_essence_recognizer.game_data.models.v2 import StatType
    from endfield_essence_recognizer.schemas.user_setting import KeepBestMode

    mode = KeepBestMode(request.mode)
    stat_type_map = {
        "ATTRIBUTE": StatType.ATTRIBUTE,
        "SECONDARY": StatType.SECONDARY,
        "SKILL": StatType.SKILL,
    }
    results: list[int] = []
    for item in request.items:
        parsed_types: list[StatType | None] = [
            stat_type_map.get(t) if t else None for t in item.stat_types
        ]
        result = compare_levels(
            item.current_levels, item.existing_levels, mode, parsed_types
        )
        results.append(result)
    return CompareLevelsResponse(results=results)


# --- 武器总览过滤器 ---


VALID_RARITY_FILTERS = ("3star", "4star", "5star", "6star", "custom")


class UpdateWeaponOverviewFiltersRequest(BaseModel):
    """更新武器总览星级过滤器的请求体。"""

    filters: dict[str, bool] = Field(
        default_factory=lambda: dict.fromkeys(VALID_RARITY_FILTERS, True)
    )

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value: dict[str, bool]) -> dict[str, bool]:
        """校验并补齐星级过滤器配置。"""
        unknown = set(value) - set(VALID_RARITY_FILTERS)
        if unknown:
            raise ValueError(f"未知星级过滤器: {sorted(unknown)}")
        return {key: bool(value.get(key, True)) for key in VALID_RARITY_FILTERS}


@router.post("/weapon_overview_filters")
async def update_weapon_overview_filters(
    request: UpdateWeaponOverviewFiltersRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的武器总览过滤器配置。"""
    return manager.update_weapon_overview_filters(request.filters)


class UpdateMatrixPlannerFarmingLocationsRequest(BaseModel):
    """更新基质规划刷取地点筛选的请求体。"""

    locations: dict[str, bool] = Field(default_factory=dict)


@router.post("/matrix_planner_farming_locations")
async def update_matrix_planner_farming_locations(
    request: UpdateMatrixPlannerFarmingLocationsRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的基质规划刷取地点筛选配置。"""
    return manager.update_matrix_planner_farming_locations(request.locations)


VALID_SWITCH_MODES: Final = {"chip", "dot", "off"}


class UpdateSwitchDisplayModeRequest(BaseModel):
    """更新"可切换"提示显示模式的请求体。"""

    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in VALID_SWITCH_MODES:
            raise ValueError(
                f"未知显示模式: {value}，可选: {sorted(VALID_SWITCH_MODES)}"
            )
        return value


@router.post("/switch_display_mode")
async def update_switch_display_mode(
    request: UpdateSwitchDisplayModeRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的"可切换"提示显示模式。"""
    return manager.update_switch_display_mode(request.mode)


VALID_MATRIX_BADGE_MODES: Final = {"small", "medium", "off"}


class UpdateMatrixBadgeDisplayModeRequest(BaseModel):
    """更新基质图标显示模式的请求体。"""

    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in VALID_MATRIX_BADGE_MODES:
            raise ValueError(
                f"未知显示模式: {value}，可选: {sorted(VALID_MATRIX_BADGE_MODES)}"
            )
        return value


@router.post("/matrix_badge_display_mode")
async def update_matrix_badge_display_mode(
    request: UpdateMatrixBadgeDisplayModeRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的基质图标显示模式。"""
    return manager.update_matrix_badge_display_mode(request.mode)


class UpdateWeaponPriorityRequest(BaseModel):
    """更新单把武器优先级的请求体。"""

    weapon_id: str
    priority: int = Field(default=0, ge=0, le=9)


@router.post("/weapon_priority")
async def update_weapon_priority(
    request: UpdateWeaponPriorityRequest,
    manager: ProfileManager = Depends(get_profile_manager),
) -> ProfileData:
    """更新当前激活账号的单个武器优先级。"""
    return manager.update_weapon_priority(request.weapon_id, request.priority)
