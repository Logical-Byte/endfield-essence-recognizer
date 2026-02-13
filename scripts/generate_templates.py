import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to sys.path to allow importing from the legacy package
sys.path.append(str(Path(__file__).parent))

from legacy_game_data.weapon import (
    all_attribute_stats,
    all_secondary_stats,
    all_skill_stats,
    get_gem_tag_name,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate essence recognition templates."
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=Path("src/endfield_essence_recognizer/templates/generated"),
        help="Directory where generated templates will be saved.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Avoid writing files to disk; only print what would be done.",
    )
    args = parser.parse_args()
    font_path = r"C:\Windows\Fonts\HarmonyOS_SansSC_Regular.ttf"
    if not Path(font_path).exists():
        print(f"Font file not found: {font_path}")
        sys.exit(1)
    font = ImageFont.truetype(font_path, size=22)

    for label in all_attribute_stats + all_secondary_stats + all_skill_stats:
        text = get_gem_tag_name(label, "CN")
        image = Image.new("L", (160, 24), color=0)
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text, font=font, fill=255)

        save_path = args.output_dir / f"{label}.png"

        if args.dry_run:
            print(f"[DRY RUN] Would save template image: {save_path} for label: {text}")
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(save_path)
            print(f"Saved template image: {save_path}")


if __name__ == "__main__":
    main()
