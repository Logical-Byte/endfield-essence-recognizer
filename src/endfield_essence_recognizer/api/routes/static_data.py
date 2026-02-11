from fastapi import APIRouter, Depends, HTTPException

from endfield_essence_recognizer.dependencies.services import get_static_data_service
from endfield_essence_recognizer.schemas.static_data import (
    EssenceInfo,
    EssenceListResponse,
    RarityColorResponse,
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


@router.get("/essences/{essence_id}")
async def get_essence(
    essence_id: str,
    service: StaticDataService = Depends(get_static_data_service),
) -> EssenceInfo:
    """
    Get information for a specific essence (gem).
    """
    essence = service.get_essence(essence_id)
    if not essence:
        raise HTTPException(status_code=404, detail="Essence not found")
    return essence


@router.get("/essences")
async def list_essences(
    service: StaticDataService = Depends(get_static_data_service),
) -> EssenceListResponse:
    """
    List all available essences.
    """
    return service.list_essences()
