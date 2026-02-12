from endfield_essence_recognizer.game_data import (
    gem_table,
    get_translation,
    item_table,
    rarity_color_table,
    weapon_basic_table,
    wiki_entry_data_table,
    wiki_entry_table,
    wiki_group_table,
)
from endfield_essence_recognizer.game_data.weapon import get_stats_for_weapon
from endfield_essence_recognizer.schemas.static_data import (
    EssenceInfo,
    EssenceListResponse,
    EssenceType,
    RarityColorResponse,
    WeaponInfo,
    WeaponListResponse,
    WeaponTypeInfo,
    WeaponTypeListResponse,
)


class StaticDataService:
    """
    Static data service for retrieving game-related information.

    TODO: Refactor the database schema (smaller jsons) before testing this service.
    """

    def __init__(self):
        self.language = "CN"
        self.item_icon_base_url = "https://cos.yituliu.cn/endfield/unpack-images/items/"
        self.group_icon_base_url = (
            "https://cos.yituliu.cn/endfield/sprites_selective/wiki/groupicon/"
        )

    def _get_item_icon_url(self, icon_id: str | None) -> str:
        if not icon_id:
            return ""
        return f"{self.item_icon_base_url}{icon_id}.webp"

    def _get_group_icon_url(self, icon_id: str | None) -> str:
        if not icon_id:
            return ""
        return f"{self.group_icon_base_url}{icon_id}.png"

    def get_weapon(self, weapon_id: str) -> WeaponInfo | None:
        """
        Get detailed information for a specific weapon.

        Args:
            weapon_id: The unique identifier for the weapon (e.g., 'wpn_funnel_0009').

        Returns:
            A WeaponInfo object containing name, rarity, icon, and essence stats,
            or None if the weapon is not found.
        """
        item = item_table.get(weapon_id)
        if not item:
            return None

        weapon_basic = weapon_basic_table.get(weapon_id)
        if not weapon_basic:
            return None

        stats = get_stats_for_weapon(weapon_id)

        return WeaponInfo(
            id=weapon_id,
            name=get_translation(item["name"], self.language),
            icon_url=self._get_item_icon_url(item.get("iconId")),
            rarity=item.get("rarity", 0),
            attribute_essence_id=stats.get("attribute"),
            secondary_essence_id=stats.get("secondary"),
            skill_essence_id=stats.get("skill"),
        )

    def list_weapons(self, weapon_type_id: str | None = None) -> WeaponListResponse:
        """
        List weapons, optionally filtered by their weapon type.

        Args:
            weapon_type_id: Optional Wiki Group ID (e.g., 'wiki_group_weapon_sword') to filter results.

        Returns:
            A WeaponListResponse containing the list of matching weapons.
        """
        weapons = []

        # If weapon_type_id (groupId) is provided, we filter by wiki entries
        if weapon_type_id:
            entries = wiki_entry_table.get(weapon_type_id, {}).get("list", [])
            for entry_id in entries:
                entry_data = wiki_entry_data_table.get(entry_id)
                if entry_data:
                    weapon_id = entry_data.get("refItemId")
                    if weapon_id:
                        weapon_info = self.get_weapon(weapon_id)
                        if weapon_info:
                            weapons.append(weapon_info)
        else:
            # Otherwise return all weapons in weapon_basic_table
            for weapon_id in weapon_basic_table.keys():
                weapon_info = self.get_weapon(weapon_id)
                if weapon_info:
                    weapons.append(weapon_info)

        return WeaponListResponse(weapons=weapons)

    def list_weapon_types(self) -> WeaponTypeListResponse:
        """
        List all available weapon categories (types) and their associated weapons.

        Returns:
            A WeaponTypeListResponse containing category metadata and weapon IDs.
        """
        weapon_types = []
        # Get all weapon groups from wiki_group_table. Each group represents a weapon type.
        groups = wiki_group_table.get("wiki_type_weapon", {}).get("list", [])

        for i, group in enumerate(groups):
            group_id = group.get("groupId")
            if group_id is None:
                continue
            # The wiki entries of this weapon type
            entries = wiki_entry_table.get(group_id, {}).get("list", [])

            weapon_ids = []
            for entry_id in entries:
                entry_data = wiki_entry_data_table.get(entry_id)
                if entry_data:
                    ref_item_id = entry_data.get("refItemId")
                    if ref_item_id:
                        weapon_ids.append(ref_item_id)

            weapon_types.append(
                WeaponTypeInfo(
                    id=group_id,
                    name=get_translation(group["groupName"], self.language),
                    icon_url=self._get_group_icon_url(group.get("iconId")),
                    sort_order=i,
                    weapon_ids=weapon_ids,
                )
            )

        return WeaponTypeListResponse(weapon_types=weapon_types)

    def get_rarity_colors(self) -> RarityColorResponse:
        """
        Get the mapping between item rarity levels and their corresponding hex colors.

        Returns:
            A RarityColorResponse mapping integers (1-6) to hex strings.
        """
        colors = {}
        for rarity, data in rarity_color_table.items():
            try:
                r_int = int(rarity)
                colors[r_int] = f"#{data.get('color', 'FFFFFF')}"
            except ValueError:
                continue
        return RarityColorResponse(colors=colors)

    def get_essence(self, essence_id: str) -> EssenceInfo | None:
        """
        Get information for a specific essence (gem).

        Args:
            essence_id: The unique identifier for the essence (gemTermId).

        Returns:
            An EssenceInfo object containing name, tag name and type, or None if not found.
        """
        gem = gem_table.get(essence_id)
        if not gem:
            return None

        tag_name_data = gem.get("tagName")
        if not tag_name_data:
            return None

        # termType: 0=Attribute, 1=Secondary, 2=Skill
        match gem.get("termType", None):
            case 0:
                essence_type = EssenceType.ATTRIBUTE
            case 1:
                essence_type = EssenceType.SECONDARY
            case 2:
                essence_type = EssenceType.SKILL
            case _:
                return None  # Unknown term type

        name = get_translation(tag_name_data, self.language)

        return EssenceInfo(
            id=essence_id,
            name=name,
            tag_name=name,
            type=essence_type,
        )

    def list_essences(self) -> EssenceListResponse:
        """
        List all available essences (gems).

        Returns:
            An EssenceListResponse containing the full list of essences.
        """
        essences = []
        for gem_id in gem_table.keys():
            essence = self.get_essence(gem_id)
            if essence:
                essences.append(essence)
        return EssenceListResponse(essences=essences)
