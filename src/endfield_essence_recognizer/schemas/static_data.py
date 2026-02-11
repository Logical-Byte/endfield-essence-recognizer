from enum import StrEnum

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

type EssenceId = str
"""
表示基质的唯一标识符 (gemTermId)。
"""


class EssenceType(StrEnum):
    ATTRIBUTE = "ATTRIBUTE"
    SECONDARY = "SECONDARY"
    SKILL = "SKILL"


class WeaponInfo(BaseModel):
    id: str = Field(description="武器的唯一标识符")
    name: str = Field(description="武器名称")
    icon_url: str = Field(description="武器图片的URL")
    rarity: int = Field(description="武器稀有度，整数表示")
    attribute_essence_id: EssenceId | None = Field(
        default=None, description="表示武器基础属性的基质ID"
    )
    secondary_essence_id: EssenceId | None = Field(
        default=None, description="表示武器次要属性的基质ID"
    )
    skill_essence_id: EssenceId | None = Field(
        default=None, description="表示武器技能属性的基质ID"
    )

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class WeaponTypeInfo(BaseModel):
    id: str = Field(description="武器类型百科组 ID (groupId)")
    name: str = Field(description="武器类型名称，如单手剑、双手剑等")
    icon_url: str = Field(description="武器类型图标的URL")
    sort_order: int = Field(description="武器类型的排序顺序")
    weapon_ids: list[str] = Field(description="属于该类型的武器 ID 列表")

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class EssenceInfo(BaseModel):
    id: EssenceId = Field(description="基质的唯一标识符")
    name: str = Field(description="基质名称")
    tag_name: str = Field(description="基质标签名称 (tagName)")
    type: EssenceType = Field(description="基质类型")

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class WeaponListResponse(BaseModel):
    weapons: list[WeaponInfo] = Field(description="武器列表")

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class WeaponTypeListResponse(BaseModel):
    weapon_types: list[WeaponTypeInfo] = Field(description="武器类型列表")

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class EssenceListResponse(BaseModel):
    essences: list[EssenceInfo] = Field(description="基质列表")

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )


class RarityColorResponse(BaseModel):
    colors: dict[int, str] = Field(description="稀有度到颜色代码的映射")
