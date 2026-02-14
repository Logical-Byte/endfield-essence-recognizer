from fastapi import APIRouter, Depends, HTTPException

from endfield_essence_recognizer.dependencies.services import get_static_data_service
from endfield_essence_recognizer.schemas.static_data import (
    RarityColorResponse,
    StatInfo,
    StatListResponse,
    WeaponInfo,
    WeaponListResponse,
    WeaponTypeListResponse,
)
from endfield_essence_recognizer.services.static_data_service import StaticDataService

router = APIRouter(prefix="/static", tags=["static_data"])


@router.get("/weapons/{weapon_id}")
async def get_weapon(
    weapon_id: str,
    service: StaticDataService = Depends(get_static_data_service),
) -> WeaponInfo:
    """
    Get information for a specific weapon.
    """
    weapon = service.get_weapon(weapon_id)
    if not weapon:
        raise HTTPException(status_code=404, detail="Weapon not found")
    return weapon


@router.get("/weapons")
async def list_weapons(
    weapon_type_id: str | None = None,
    service: StaticDataService = Depends(get_static_data_service),
) -> WeaponListResponse:
    """
    List all weapons, optionally filtered by weapon type (Wiki Group ID).
    """
    return service.list_weapons(weapon_type_id=weapon_type_id)


@router.get("/weapon_types")
async def list_weapon_types(
    service: StaticDataService = Depends(get_static_data_service),
) -> WeaponTypeListResponse:
    """
    List all weapon categories and their associated weapon IDs.
    """
    return service.list_weapon_types()


@router.get("/rarity_colors")
async def get_rarity_colors(
    service: StaticDataService = Depends(get_static_data_service),
) -> RarityColorResponse:
    """
    Get the rarity level to hex color mapping.
    """
    return service.get_rarity_colors()


@router.get("/essences/{stat_id}")
async def get_essence(
    stat_id: str,
    service: StaticDataService = Depends(get_static_data_service),
) -> StatInfo:
    """
    Get information for a specific essence (stat).
    """
    essence = service.get_essence(stat_id)
    if not essence:
        raise HTTPException(status_code=404, detail="Stat not found")
    return essence


@router.get("/essences")
async def list_essences(
    service: StaticDataService = Depends(get_static_data_service),
) -> StatListResponse:
    """
    List all available essences.
    """
    return service.list_essences()
