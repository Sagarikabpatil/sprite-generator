"""Create a semantically curated character dataset from the stricter character_clean set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.datasets.semantic_filter import DEFAULT_THRESHOLD, apply_semantic_filter

INPUT_DIR = BASE_DIR / "data" / "character_clean"
INPUT_IMAGES_DIR = INPUT_DIR / "images"
INPUT_METADATA_PATH = INPUT_DIR / "metadata" / "metadata.jsonl"
OUTPUT_DIR = BASE_DIR / "data" / "character_curated"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_METADATA_DIR = OUTPUT_DIR / "metadata"
OUTPUT_VALIDATION_DIR = OUTPUT_DIR / "validation"
MODEL_USED = "openai/clip-vit-base-patch32"


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


def export_metadata(metadata_path: Path, records: list[dict[str, str]]) -> None:
    with metadata_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    if not INPUT_IMAGES_DIR.exists():
        raise FileNotFoundError(f"Input character images directory not found: {INPUT_IMAGES_DIR}")

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    metadata_map = load_metadata_map(INPUT_METADATA_PATH)
    files = sorted(INPUT_IMAGES_DIR.glob("*.png"), key=lambda item: int(item.stem))

    accepted_records: list[dict[str, str]] = []
    example_rejections: list[dict[str, Any]] = []
    accepted_count = 0
    rejected_count = 0

    for image_path in files:
        caption = metadata_map.get(image_path.name, "")
        try:
            with image_path.open("rb") as handle:
                image_bytes = handle.read()
        except OSError:
            rejected_count += 1
            example_rejections.append({"file_name": image_path.name, "score": -1.0, "reason": "read_error"})
            continue

        accepted, score, _prompt_scores = apply_semantic_filter(image_bytes, threshold=DEFAULT_THRESHOLD)
        if accepted:
            target_path = OUTPUT_IMAGES_DIR / image_path.name
            target_path.write_bytes(image_bytes)
            accepted_records.append({
                "file_name": f"images/{image_path.name}",
                "text": caption,
            })
            accepted_count += 1
        else:
            rejected_count += 1
            if len(example_rejections) < 10:
                example_rejections.append({
                    "file_name": image_path.name,
                    "score": float(score),
                    "reason": "semantic_score_below_threshold",
                })

    export_metadata(OUTPUT_METADATA_DIR / "metadata.jsonl", accepted_records)

    acceptance_rate = (accepted_count / len(files)) if files else 0.0
    report = {
        "input_count": len(files),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "acceptance_rate": acceptance_rate,
        "threshold": DEFAULT_THRESHOLD,
        "model_used": MODEL_USED,
        "example_rejections": example_rejections,
    }
    report_path = OUTPUT_VALIDATION_DIR / "curated_dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Character dataset preparation complete.")
    print(f"Input: {len(files)}")
    print(f"Accepted: {accepted_count}")
    print(f"Rejected: {rejected_count}")
    print(f"Acceptance rate: {acceptance_rate:.3f}")
    print(f"Threshold: {DEFAULT_THRESHOLD}")
    print(f"Model: {MODEL_USED}")


if __name__ == "__main__":
    main()
