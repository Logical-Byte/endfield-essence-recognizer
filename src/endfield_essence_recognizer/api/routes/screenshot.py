from pathlib import Path

from fastapi import APIRouter, Depends

from endfield_essence_recognizer.core.layout import ResolutionProfile
from endfield_essence_recognizer.dependencies import (
    get_resolution_profile_dep,
    get_screenshot_service,
    get_screenshots_dir_dep,
)
from endfield_essence_recognizer.models.screenshot import (
    ImageFormat,
    ScreenshotRequest,
    ScreenshotResponse,
)
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService
from endfield_essence_recognizer.utils.log import logger

router = APIRouter(prefix="", tags=["screenshot"])


@router.get("/screenshot")
async def get_screenshot(
    width: int = 1920,
    height: int = 1080,
    format: ImageFormat = ImageFormat.JPG,  # noqa: A002
    quality: int = 75,
    screenshot_service: ScreenshotService = Depends(get_screenshot_service),
) -> str | None:
    try:
        return await screenshot_service.capture_as_data_uri(
            width=width, height=height, format=format, quality=quality
        )
    except Exception as e:
        logger.exception(f"Failed to capture screenshot: {e}")
        return None


@router.post(
    "/take_and_save_screenshot",
    description="后端截图并保存到本地，返回文件路径和文件名",
)
async def take_and_save_screenshot(
    request: ScreenshotRequest,
    screenshot_dir: Path = Depends(get_screenshots_dir_dep),
    resolution_profile: ResolutionProfile = Depends(get_resolution_profile_dep),
    screenshot_service: ScreenshotService = Depends(get_screenshot_service),
) -> ScreenshotResponse:
    """Takes a screenshot and saves it to a local directory."""
    try:
        full_path, file_name = await screenshot_service.capture_and_save(
            screenshot_dir=screenshot_dir,
            resolution_profile=resolution_profile,
            should_focus=request.should_focus,
            post_process=request.post_process,
            title=request.title,
            fmt=request.format,
        )
        return ScreenshotResponse(
            success=True,
            message="Screenshot saved successfully.",
            file_path=full_path,
            file_name=file_name,
        )
    except Exception as e:
        logger.exception(f"Failed to take and save screenshot: {e}")
        return ScreenshotResponse(
            success=False,
            message=str(e),
            file_path=None,
            file_name=None,
        )
