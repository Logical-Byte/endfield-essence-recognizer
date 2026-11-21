"""自定义能量淤积点（刷取地点）。

游戏小版本新增淤积点时，内置数据（`resources/data/v2/EnergyAlluviums.json`）
要等静态数据表更新后才能参与规划。自定义条目让用户先自己补上，落盘在程序根
目录的 `custom_alluviums.json`，属于全局用户数据：不随账号切换，全账号通用。
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, field_validator

#: 自定义淤积点在各账号刷取地点筛选配置（`matrix_planner_farming_locations`）
#: 中的 key 前缀，其后拼接稳定 ID。前端按同一规则生成 battleId。
CUSTOM_ALLUVIUM_ID_PREFIX: Final[str] = "custom_alluvium:"

#: 单组词条列表的长度上限。
#:
#: 规划器会把基础属性展开成 C(n,3) 个预刻组合，词条越多组合数涨得越快；界面
#: 最多只能勾出静态数据里的全部词条（基础 5 / 附加 12 / 技能 14 项），因此这个
#: 上限只用于拦住手改文件或异常请求塞进来的超长池，留足了小版本新增词条的余地。
MAX_STAT_POOL_SIZE: Final[int] = 32


class CustomAlluvium(BaseModel):
    """一条用户自定义的能量淤积点。"""

    id: str = ""
    """稳定标识符，创建时生成后不再变化。

    各账号的刷取地点筛选以 `custom_alluvium:{id}` 为键，用列表下标做标识会让
    每次删除都必须重写所有下游引用。空字符串表示尚未分配（手工编辑的配置），
    由 `CustomAlluviumManager` 在读取时补齐。
    """

    name: str = ""
    """显示名称；为空时前端退化为「自定义淤积点 N」。"""

    attribute_stats: list[str] = []
    """该地点可刷出的基础属性词条 ID。

    为空表示不限制（按全部基础属性计算，与内置地点口径一致）。
    """

    secondary_stats: list[str] = []
    """该地点可刷出的附加属性词条 ID。"""

    skill_stats: list[str] = []
    """该地点可刷出的技能属性词条 ID。"""

    @field_validator("attribute_stats", "secondary_stats", "skill_stats")
    @classmethod
    def _normalize_stats(cls, stats: list[str]) -> list[str]:
        """去重（保持原顺序）并限制长度。

        重复词条会让规划器对同一条附加/技能属性重复生成方案；基础属性去重后
        不足三项还会退化成「不限制」，与用户的勾选意图相反。落盘与手改文件都
        走模型校验，因此在这里统一收敛。

        Raises:
            ValueError: 词条数量超过 `MAX_STAT_POOL_SIZE`。
        """
        unique = list(dict.fromkeys(stats))
        if len(unique) > MAX_STAT_POOL_SIZE:
            raise ValueError(f"单组词条不能超过 {MAX_STAT_POOL_SIZE} 项")
        return unique
