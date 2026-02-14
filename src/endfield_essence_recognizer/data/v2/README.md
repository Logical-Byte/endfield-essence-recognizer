# Game Data V2 (Transformed)

This directory contains transformed and joined game data optimized for performance and type safety. These files are generated from the raw game tables in `../endfielddata/TableCfg/` using the `scripts/transform_weapon_data.py` script.

## Schema Overview

All text fields use the **Simplified Chinese (CN)** version of the game's i18n data. Data is stored in JSON files as dictionaries keyed by their Primary Key.

### 1. Weapon (`Weapon.json`)
Represents a weapon in the game.
- **`weapon_id`** (string, PK): Original item/weapon ID (e.g., `wpn_funnel_0009`).
- **`name`** (string): The display name of the weapon in CN.
- **`weapon_type`** (integer, FK): Reference to `WeaponType.json`.
- **`rarity`** (integer): The rarity levels (e.g., 3, 4, 5).
- **`stat1_id`** (string | null, FK): Reference to `EssenceStat.json` (Attribute slot).
- **`stat2_id`** (string | null, FK): Reference to `EssenceStat.json` (Secondary slot).
- **`stat3_id`** (string | null, FK): Reference to `EssenceStat.json` (Skill slot).

### 2. EssenceStat (`EssenceStat.json`)
Represents an individual essence entry or sub-stat/skill.
- **`stat_id`** (string, PK): Unique identifier for the essence.
- **`name`** (string): The display name of the essence effect in CN.
- **`type`** (string): Enum: `ATTRIBUTE`, `SECONDARY`, `SKILL`.

### 3. WeaponType (`WeaponType.json`)
Categorizes weapons into archetypes (e.g., Sword, Staff).
- **`weapon_type_id`** (integer, PK): Unique identifier.
- **`wiki_group_id`** (string): Backward-compatibility identifier (e.g., `wiki_group_weapon_sword`).
- **`name`** (string): Display name of the weapon type in CN.

### 4. RarityColor (`RarityColor.json`)
Maps weapon rarity levels to their associated color codes.

## Usage

These files are indexed and queried by the `StaticGameData` manager class. Avoid reading these files directly in feature logic; use the provided repository/service layer instead.

## Maintenance

To update these files when raw game data changes:
1. Ensure the raw tables in `src/endfield_essence_recognizer/data/endfielddata/TableCfg/` are up to date.
2. Run the transformation script:
   ```bash
   uv run python .\scripts\transform_weapon_data.py .\src\endfield_essence_recognizer\data\endfielddata\TableCfg\ .\src\endfield_essence_recognizer\data\v2\
   ```
We may introduce other tools to insert new data or validate existing data in the future.
