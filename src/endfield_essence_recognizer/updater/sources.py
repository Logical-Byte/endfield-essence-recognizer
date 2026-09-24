"""更新流程开关与选择顺序。"""

from __future__ import annotations

YITULIU_FLOW = "cn_yituliu"
MIRROR_CHYAN_FLOW = "cn_mirrorchyan"
GITHUB_FLOW = "github"

UPDATE_FLOW_NAMES = {
    YITULIU_FLOW: "一图流 API (CN 镜像)",
    MIRROR_CHYAN_FLOW: "Mirror 酱",
    GITHUB_FLOW: "GitHub Release",
}

# 字典顺序即检查失败后的回退顺序。
UPDATE_FLOW_ENABLED = {
    YITULIU_FLOW: True,
    MIRROR_CHYAN_FLOW: False,
    GITHUB_FLOW: True,
}

# 仅作为启动自动检查和无效配置时的首选流程。
DEFAULT_UPDATE_FLOW = GITHUB_FLOW

LEGACY_FLOW_ALIASES = {
    "cn": YITULIU_FLOW,
}


def get_enabled_update_flows() -> list[str]:
    """按配置顺序返回启用的更新流程。"""
    return [flow for flow, enabled in UPDATE_FLOW_ENABLED.items() if enabled]


def normalize_update_flow(value: str | None) -> str:
    """规范化更新流程；无效值回退到默认或首个启用流程。"""
    flow = LEGACY_FLOW_ALIASES.get(str(value or ""), str(value or ""))
    enabled = get_enabled_update_flows()
    if flow in enabled:
        return flow
    if DEFAULT_UPDATE_FLOW in enabled:
        return DEFAULT_UPDATE_FLOW
    return enabled[0] if enabled else DEFAULT_UPDATE_FLOW


def build_update_flow_order(preferred: str | None = None) -> list[str]:
    """构建本次检查顺序：首选流程优先，其余按 UPDATE_FLOW_ENABLED 顺序。"""
    enabled = get_enabled_update_flows()
    if not enabled:
        return []

    first = normalize_update_flow(preferred)
    if first not in enabled:
        first = normalize_update_flow(DEFAULT_UPDATE_FLOW)

    ordered = [first]
    ordered.extend(flow for flow in enabled if flow != first)
    return ordered
