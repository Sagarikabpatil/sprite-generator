"""Prepare a stricter character-focused subset from the existing clean dataset."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.datasets.character_filter import evaluate_character_candidate, is_character_candidate

INPUT_DIR = BASE_DIR / "data" / "clean"
IMAGE_INPUT_DIR = INPUT_DIR / "images"
METADATA_INPUT_PATH = INPUT_DIR / "metadata" / "metadata.jsonl"
OUTPUT_DIR = BASE_DIR / "data" / "character_clean"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_METADATA_DIR = OUTPUT_DIR / "metadata"
OUTPUT_VALIDATION_DIR = OUTPUT_DIR / "validation"


def load_metadata_map(metadata_path: Path) -> dict[str, str]:
    metadata_map: dict[str, str] = {}
    if not metadata_path.exists():
        return metadata_map

    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        file_name = record.get("file_name", "")
        if not file_name:
            continue
        relative_name = file_name.split("/")[-1]
        metadata_map[relative_name] = record.get("text") or ""
    return metadata_map


def export_metadata(metadata_path: Path, accepted_entries: list[dict[str, str]]) -> None:
    with metadata_path.open("w", encoding="utf-8") as handle:
        for entry in accepted_entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    if not IMAGE_INPUT_DIR.exists():
        raise FileNotFoundError(f"Input dataset images directory not found: {IMAGE_INPUT_DIR}")

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    metadata_map = load_metadata_map(METADATA_INPUT_PATH)
    files = sorted(IMAGE_INPUT_DIR.glob("*.png"), key=lambda item: int(item.stem))

    accepted_entries: list[dict[str, str]] = []
    rejection_reasons: Counter[str] = Counter()
    accepted_count = 0
    rejected_count = 0

    for image_path in files:
        caption = metadata_map.get(image_path.name, "")
        try:
            candidate = image_path.read_bytes()
        except OSError:
            rejection_reasons["invalid_image"] += 1
            rejected_count += 1
            continue

        ok, reasons = evaluate_character_candidate(candidate, caption)
        if ok and is_character_candidate(candidate, caption):
            target_path = OUTPUT_IMAGES_DIR / image_path.name
            target_path.write_bytes(candidate)
            accepted_entries.append({
                "file_name": f"images/{image_path.name}",
                "text": caption,
            })
            accepted_count += 1
            continue

        rejected_count += 1
        if not reasons:
            reasons = ["poor_composition"]
        for reason in reasons:
            rejection_reasons[reason] += 1

    export_metadata(OUTPUT_METADATA_DIR / "metadata.jsonl", accepted_entries)

    report = {
        "input_count": len(files),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "final_count": accepted_count,
    }
    report_path = OUTPUT_VALIDATION_DIR / "character_dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Character dataset preparation complete.")
    print("Input:")
    print(len(files))
    print("Accepted:")
    print(accepted_count)
    print("Rejected:")
    print(rejected_count)
    print("Rejection reasons:")
    for key, value in sorted(rejection_reasons.items()):
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
