"""Prepare a clean, validation-passed training dataset from the character dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.datasets.exporter import export_clean_dataset
from app.datasets.filter import filter_dataset
from app.datasets.loader import get_dataset_statistics, load_character_dataset
from app.datasets.validator import validate_caption, validate_image

VALIDATION_DIR = BASE_DIR / "data" / "validation"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    dataset = load_character_dataset()
    stats = get_dataset_statistics(dataset)
    print("Dataset statistics:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    safe_dataset = filter_dataset(dataset)

    valid_records = []
    invalid_count = 0
    for sample in safe_dataset:
        image = sample.get("image")
        caption = sample.get("text") or sample.get("caption") or sample.get("prompt")
        if not validate_image(image):
            invalid_count += 1
            continue
        if not validate_caption(caption):
            invalid_count += 1
            continue
        valid_records.append({
            "image": image,
            "text": caption,
        })

    export_clean_dataset(valid_records)

    report = {
        "source_dataset": "Limbicnation/pixel-art-character",
        "original_count": len(dataset),
        "safe_count": len(safe_dataset),
        "filtered_count": len(dataset) - len(safe_dataset),
        "valid_count": len(valid_records),
        "invalid_count": invalid_count,
        "duplicate_count": 0,
        "final_count": len(valid_records),
    }

    report_path = VALIDATION_DIR / "dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Dataset preparation complete.")
    print(f"Original: {report['original_count']}")
    print(f"Safe: {report['safe_count']}")
    print(f"Invalid: {report['invalid_count']}")
    print(f"Duplicates: {report['duplicate_count']}")
    print(f"Final training samples: {report['final_count']}")


if __name__ == "__main__":
    main()
