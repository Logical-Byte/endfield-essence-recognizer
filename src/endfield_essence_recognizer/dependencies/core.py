from fastapi import Depends

from endfield_essence_recognizer.core.delivery_claimer.engine import (
    DeliveryClaimerEngine,
)
from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.layout.factory import (
    build_resolution_profile,
)
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusRecognizer,
    AttributeLevelRecognizer,
    AttributeRecognizer,
    DeliveryJobRewardRecognizer,
    DeliverySceneRecognizer,
    LockStatusRecognizer,
    UISceneRecognizer,
)
from endfield_essence_recognizer.core.scanner.context import (
    ScannerContext,
)
from endfield_essence_recognizer.core.scanner.engine import (
    OneTimeRecognitionEngine,
    ScannerEngine,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.core.window.adapter import WindowActionsAdapter
from endfield_essence_recognizer.core.window.scaling import (
    ScalingImageSource,
    ScalingWindowActions,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.services.audio_service import AudioService
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

from .recognition import (
    get_abandon_status_recognizer_dep,
    get_attribute_level_recognizer_dep,
    get_attribute_recognizer_dep,
    get_delivery_job_reward_recognizer_dep,
    get_delivery_scene_recognizer_dep,
    get_lock_status_recognizer_dep,
    get_ui_scene_recognizer_dep,
)
from .services import (
    get_audio_service,
    get_static_game_data,
)
from .settings import (
    get_user_setting_manager_dep,
)
from .window import get_game_window_manager


def get_resolution_profile_dep(
    window_manager: WindowManager = Depends(get_game_window_manager),
) -> ResolutionProfile:
    """
    FastAPI dependency: The layout configuration corresponding to the current game window resolution.

    Raises:
        WindowNotFoundError: If the target window is not found.
        ValueError: If the screen width or height is not a positive integer.
    """
    w, h = window_manager.get_client_size()
    logical_w = round(w * 1080 / h)
    return build_resolution_profile(logical_w, 1080)


def get_resolution_profile() -> ResolutionProfile:
    """
    A non-dependency version of get_resolution_profile_dep.
    """
    return get_resolution_profile_dep(window_manager=get_game_window_manager())


def get_scanner_context_dep(
    attr_recognizer: AttributeRecognizer = Depends(get_attribute_recognizer_dep),
    attr_level_recognizer: AttributeLevelRecognizer = Depends(
        get_attribute_level_recognizer_dep
    ),
    abandon_status_recognizer: AbandonStatusRecognizer = Depends(
        get_abandon_status_recognizer_dep
    ),
    lock_status_recognizer: LockStatusRecognizer = Depends(
        get_lock_status_recognizer_dep
    ),
    ui_scene_recognizer: UISceneRecognizer = Depends(get_ui_scene_recognizer_dep),
    static_data: StaticGameData = Depends(get_static_game_data),
) -> ScannerContext:
    """
    Get a ScannerContext instance.
    """
    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
        static_game_data=static_data,
    )


def get_scanner_engine_dep(
    ctx: ScannerContext = Depends(get_scanner_context_dep),
    window_manager: WindowManager = Depends(get_game_window_manager),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
    profile: ResolutionProfile = Depends(get_resolution_profile_dep),
) -> ScannerEngine:
    """
    Get a ScannerEngine instance with scaling middleware.
    """
    adapter = WindowActionsAdapter(window_manager)
    image_source = ScalingImageSource(adapter)
    window_actions = ScalingWindowActions(adapter, image_source)
    return ScannerEngine(
        ctx=ctx,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=user_setting_manager,
        profile=profile,
    )


def get_one_time_recognition_engine_dep(
    ctx: ScannerContext = Depends(get_scanner_context_dep),
    window_manager: WindowManager = Depends(get_game_window_manager),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
    profile: ResolutionProfile = Depends(get_resolution_profile_dep),
) -> OneTimeRecognitionEngine:
    """
    Get a OneTimeRecognitionEngine instance with scaling middleware.
    """
    adapter = WindowActionsAdapter(window_manager)
    image_source = ScalingImageSource(adapter)
    window_actions = ScalingWindowActions(adapter, image_source)
    return OneTimeRecognitionEngine(
        ctx=ctx,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=user_setting_manager,
        profile=profile,
    )


def get_delivery_claimer_engine_dep(
    window_manager: WindowManager = Depends(get_game_window_manager),
    profile: ResolutionProfile = Depends(get_resolution_profile_dep),
    delivery_scene_recognizer: DeliverySceneRecognizer = Depends(
        get_delivery_scene_recognizer_dep
    ),
    delivery_job_reward_recognizer: DeliveryJobRewardRecognizer = Depends(
        get_delivery_job_reward_recognizer_dep
    ),
    audio_service: AudioService = Depends(get_audio_service),
) -> DeliveryClaimerEngine:
    """
    Get a DeliveryClaimerEngine instance with scaling middleware.
    """
    adapter = WindowActionsAdapter(window_manager)
    image_source = ScalingImageSource(adapter)
    window_actions = ScalingWindowActions(adapter, image_source)
    return DeliveryClaimerEngine(
        image_source=image_source,
        window_actions=window_actions,
        profile=profile,
        delivery_scene_recognizer=delivery_scene_recognizer,
        delivery_job_reward_recognizer=delivery_job_reward_recognizer,
        audio_service=audio_service,
    )
