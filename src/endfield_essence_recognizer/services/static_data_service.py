from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.static_data import (
    RarityColorResponse,
    StatInfo,
    StatListResponse,
    StatType,
    WeaponInfo,
    WeaponListResponse,
    WeaponTypeInfo,
    WeaponTypeListResponse,
)


class StaticDataService:
    """
    Static data service for retrieving game-related information.
    """

    def __init__(self, data: StaticGameData):
        self.language = "CN"
        self.item_icon_base_url = "https://cos.yituliu.cn/endfield/unpack-images/items/"
        self.group_icon_base_url = (
            "https://cos.yituliu.cn/endfield/sprites_selective/wiki/groupicon/"
        )
        self.data = data

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
        weapon = self.data.get_weapon(weapon_id)
        if not weapon:
            return None

        return WeaponInfo(
            id=weapon.weapon_id,
            name=weapon.name,
            icon_url=self._get_item_icon_url(weapon.icon_id),
            rarity=weapon.rarity,
            attribute_stat_id=weapon.stat1_id,
            secondary_stat_id=weapon.stat2_id,
            skill_stat_id=weapon.stat3_id,
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

        if weapon_type_id:
            # Find the internal type ID for the given Wiki Group ID
            target_type_id = None
            for wt in self.data.list_weapon_types():
                if wt.wiki_group_id == weapon_type_id:
                    target_type_id = wt.weapon_type_id
                    break

            if target_type_id is not None:
                target_weapons = self.data.get_weapons_by_type(target_type_id)
            else:
                target_weapons = []
        else:
            target_weapons = self.data.list_weapons()

        for w in target_weapons:
            weapon_info = self.get_weapon(w.weapon_id)
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
        raw_types = self.data.list_weapon_types()

        for i, wt in enumerate(raw_types):
            # Get all weapon IDs associated with this type
            weapon_ids = [
                w.weapon_id for w in self.data.get_weapons_by_type(wt.weapon_type_id)
            ]

            weapon_types.append(
                WeaponTypeInfo(
                    id=wt.wiki_group_id,
                    name=wt.name,
                    icon_url=self._get_group_icon_url(wt.icon_id),
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
        # We check rarities from 1 to 6 as defined in the game
        for r in range(1, 7):
            colors[r] = self.data.get_rarity_color(r)
        return RarityColorResponse(colors=colors)

    def get_essence(self, essence_id: str) -> StatInfo | None:
        """
        Get information for a specific essence (stat).

        Args:
            essence_id: The unique identifier for the essence (statTermId).

        Returns:
            A StatInfo object containing name, tag name and type, or None if not found.
        """
        stat = self.data.get_stat(essence_id)
        if not stat:
            return None

        return StatInfo(
            id=stat.stat_id,
            name=stat.name,
            tag_name=stat.name,  # Simplified to name in V2
            type=StatType(stat.type),
        )

    def list_essences(self) -> StatListResponse:
        """
        List all available essences (stats).

        Returns:
            A StatListResponse containing the full list of essences.
        """
        essences = []
        for stat in self.data.list_stats():
            essence = self.get_essence(stat.stat_id)
            if essence:
                essences.append(essence)
        return StatListResponse(items=essences)
