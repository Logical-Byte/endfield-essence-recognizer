from fastapi import APIRouter, Body, Depends, HTTPException

from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_user_setting_manager_dep
from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.schemas.user_setting import UserSetting
from endfield_essence_recognizer.services.profile_manager import ProfileManager
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
    profile_manager: ProfileManager = Depends(get_profile_manager),
) -> UserSetting:
    """保存设置。

    自定义基质被删除后（逐条删除、清空全部、重合检测），各账号里指向它的
    宝藏基质条目会失去属性来源，因此保存成功后按最新配置剪除失效引用，
    让所有删除路径都与 profile 联动，而不必各自记得清理。

    白名单取自保存后的内存配置而非请求体：`update_from_user_setting` 会为
    缺失 ID 的新条目补齐稳定 ID，直接读请求体会把它们误判成孤儿。
    """
    try:
        user_setting_manager.update_from_user_setting(new_config)
    except ConfigVersionMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    profile_manager.prune_custom_stat_refs(
        set(user_setting_manager.get_custom_stat_ids())
    )
    return user_setting_manager.get_user_setting_ref()


@router.post("/reset")
async def reset_config(
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
    profile_manager: ProfileManager = Depends(get_profile_manager),
) -> UserSetting:
    """将所有设置重置为默认值。

    自定义基质会随配置清空，因此同时清理所有账号中残留的 `custom:` 引用，
    避免界面出现指向不存在基质的幽灵条目。
    """
    user_setting_manager.reset_to_default()
    profile_manager.prune_custom_stat_refs(set())
    return user_setting_manager.get_user_setting_ref()
