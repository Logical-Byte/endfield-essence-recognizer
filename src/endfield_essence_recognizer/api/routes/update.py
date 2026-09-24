"""更新相关 API 路由。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from endfield_essence_recognizer.api.websockets.update_progress import (
    reset_progress,
    update_progress,
)
from endfield_essence_recognizer.dependencies.settings import (
    get_user_setting_manager_dep,
)
from endfield_essence_recognizer.updater.checker import NoUpdateAvailable
from endfield_essence_recognizer.updater.manager import UpdateManager
from endfield_essence_recognizer.updater.mirrors import (
    GITHUB_MIRROR_NAMES,
    get_mirror_url,
)
from endfield_essence_recognizer.updater.sources import (
    GITHUB_FLOW,
    UPDATE_FLOW_NAMES,
    get_enabled_update_flows,
)
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from endfield_essence_recognizer.services.user_setting_manager import (
        UserSettingManager,
    )

router = APIRouter(prefix="/update", tags=["update"])

update_manager = UpdateManager()


def _mask_sensitive_text(text: str, *secrets: str) -> str:
    """在返回给用户前，把已知敏感值替换为脱敏占位符。"""
    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


@router.get("/mirrors")
async def get_mirrors():
    """返回 GitHub 下载镜像列表。"""
    return {
        "mirrors": [
            {"title": name, "value": key} for key, name in GITHUB_MIRROR_NAMES.items()
        ]
    }


@router.get("/flows")
async def get_update_flows():
    """返回当前启用的更新流程列表。"""
    return {
        "flows": [
            {"title": UPDATE_FLOW_NAMES[flow], "value": flow}
            for flow in get_enabled_update_flows()
        ]
    }


@router.get("/check")
async def check_update(
    setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
):
    settings = None
    try:
        # 读取用户设置，并按当前配置顺序检查更新。
        settings = setting_manager.get_user_setting()
        proxy = settings.update_proxy if settings.update_proxy else None
        mirror_cdk = getattr(settings, "update_mirrorchyan_cdk", "")

        result = await update_manager.check_and_prompt(
            proxy=proxy,
            update_flow=getattr(settings, "update_flow", None),
            mirror_chyan_res_id=getattr(settings, "update_mirrorchyan_res_id", ""),
            mirror_chyan_cdk=mirror_cdk,
            mirror_chyan_user_agent=getattr(
                settings,
                "update_mirrorchyan_user_agent",
                "",
            ),
        )

        if isinstance(result, dict):
            return {"has_update": True, "update_info": result}
        if isinstance(result, NoUpdateAvailable):
            return {"has_update": False, "error": None}
        return {
            "has_update": False,
            "error": _mask_sensitive_text(result.message, mirror_cdk, proxy or ""),
        }
    except Exception as exc:
        logger.exception("更新检查失败")
        return {
            "has_update": False,
            "error": _mask_sensitive_text(
                str(exc),
                getattr(settings, "update_mirrorchyan_cdk", "") if settings else "",
                getattr(settings, "update_proxy", "") if settings else "",
            )
            or "更新检查失败",
        }


@router.post("/install")
async def install_update_route(
    body: dict | None = None,
    setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
):
    settings = None
    try:
        skip_verify = bool((body or {}).get("skip_verify", False))

        # 读取当前用户配置，必要时仅在 GitHub 流程下改写下载镜像。
        settings = setting_manager.get_user_setting()
        proxy = settings.update_proxy if settings.update_proxy else None
        mirror_cdk = getattr(settings, "update_mirrorchyan_cdk", "")
        github_mirror = getattr(settings, "update_github_mirror", "github")

        download_url = None
        if (
            github_mirror
            and github_mirror != "github"
            and update_manager.update_info
            and update_manager.update_info.get("source") == GITHUB_FLOW
        ):
            original_url = update_manager.update_info["download_url"]
            match = re.match(
                r"https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)",
                original_url,
            )
            if match:
                owner, repo, tag, filename = match.groups()
                # 仅改写 GitHub 官方下载地址，不跨流程切换来源。
                download_url = get_mirror_url(
                    github_mirror, f"{owner}/{repo}", tag, filename
                )
                logger.info("使用 GitHub 镜像：{}", github_mirror)

        # 清空进度状态，避免上一次更新残留信息干扰当前弹窗。
        reset_progress()

        result = await update_manager.download_and_install(
            progress_callback=update_progress,
            proxy=proxy,
            download_url=download_url,
            skip_verify=skip_verify,
        )
        if not result.get("success") and isinstance(result.get("error"), str):
            result["error"] = _mask_sensitive_text(
                result["error"],
                mirror_cdk,
                proxy or "",
                download_url or "",
            )
        return result
    except Exception as exc:
        logger.exception("更新安装失败")
        return {
            "success": False,
            "error": _mask_sensitive_text(
                str(exc),
                getattr(settings, "update_mirrorchyan_cdk", "") if settings else "",
                getattr(settings, "update_proxy", "") if settings else "",
            )
            or "更新失败",
        }


@router.post("/cancel")
async def cancel_update():
    """取消当前正在进行的更新下载。"""
    try:
        cancelled = update_manager.cancel_download()
        return {"success": cancelled}
    except Exception:
        logger.exception("更新取消失败")
        return {"success": False, "error": "更新取消失败"}
