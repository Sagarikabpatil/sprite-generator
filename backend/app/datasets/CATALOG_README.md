# SpriteForge asset catalog

This directory is a structured catalog and resource area, not a downloaded image dataset. The empty category folders are ready for legally usable assets to be added later. The checked-in records in `metadata/catalog.json` are explicitly marked as `seed_catalog_only` and contain no copyrighted artwork.

## Structure

- `characters/`: human, warrior, mage, ninja, knight, archer, robot, fantasy, sci_fi, animal, monster, chibi
- `styles/`: pixel_art, cartoon, anime, chibi, retro, fantasy, sci_fi, realistic
- `environments/`: forest, dungeon, castle, village, city, space, desert, snow, battlefield
- `weapons/`: sword, axe, spear, bow, staff, dagger, gun
- `objects/`: coins, potions, treasure, doors, crates, platforms, checkpoints
- `effects/`: fire, smoke, explosion, magic, electricity, hit, healing
- `metadata/catalog.json`: searchable metadata records

## Metadata format

Each asset record uses `id`, `name`, `category`, `subcategory`, `style`, `tags`, `actions`, `source`, `artist`, and `license`. Add dimensions, quality scores, `asset_type` (`2d` or `3d`), and provenance fields when needed. Keep one stable record per asset and never omit source or license information.

## Adding an asset

1. Add the legally usable image or model below its matching category/subcategory folder.
2. Give it a stable ID and add a metadata record with the exact relative file path in a future `path` field.
3. Record the source URL, artist, license, and any attribution requirements.
4. Run the existing validation/curation scripts when preparing training data. Do not treat catalog entries as training data automatically.

## Prompt enrichment

`app/generation/prompt_catalog.py` contains reusable vocabulary for characters, styles, viewpoints, composition, environments, weapons, and effects. It only adds neutral game-asset constraints when they are absent from the user prompt and preserves the original prompt. The catalog can later provide recommendations or filtered vocabulary without changing application code.

## Current purpose

The catalog supports prompt enrichment, semantic categorization, reproducibility, discovery, and future recommendation/search functionality. It is intentionally a resource/catalog layer today rather than a custom-model training dataset.
