from fastapi import APIRouter, Body, Depends, HTTPException

from endfield_essence_recognizer.dependencies import get_user_setting_manager_dep
from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

router = APIRouter(prefix="/config", tags=["user setting"])


@router.get("")
async def get_config(
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
) -> UserSetting:
    return user_setting_manager.get_user_setting_ref()


@router.post("")
async def post_config(
    new_config: UserSetting = Body(),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
) -> UserSetting:
    try:
        user_setting_manager.update_from_user_setting(new_config)
    except ConfigVersionMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return user_setting_manager.get_user_setting_ref()
