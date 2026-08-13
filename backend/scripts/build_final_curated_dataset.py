"""Build a final conservative curated dataset from the character_clean set.

This script uses: caption-aware filtering, updated CLIP category scoring relative
margin, and existing image-quality checks. It does not modify source datasets and
it does not start any training run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.datasets.character_filter import has_reasonable_character_composition, has_sufficient_content
from app.datasets.final_curator import caption_classification, caption_rejection_reason, final_filter
from app.datasets.semantic_filter import score_character_semantics

INPUT_IMAGES_DIR = BASE_DIR / "data" / "character_clean" / "images"
INPUT_METADATA_PATH = BASE_DIR / "data" / "character_clean" / "metadata" / "metadata.jsonl"
OUTPUT_DIR = BASE_DIR / "data" / "character_curated_final"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_METADATA_DIR = OUTPUT_DIR / "metadata"
OUTPUT_VALIDATION_DIR = OUTPUT_DIR / "validation"
CLIP_THRESHOLD = 0.75


def load_metadata_map(metadata_path: Path) -> dict[str, str]:
    record_map: dict[str, str] = {}
    if not metadata_path.exists():
        return record_map
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
        record_map[file_name.split("/")[-1]] = record.get("text") or ""
    return record_map


def build_rejected_preview(rejected: list[dict[str, Any]], output_path: Path) -> None:
    if not rejected:
        Image.new("RGB", (1200, 800), color=(245, 245, 245)).save(output_path)
        return

    selected = rejected[:20]
    cell = 170
    padding = 18
    cols = 5
    rows = (len(selected) + cols - 1) // cols
    canvas_w = cols * cell + (cols + 1) * padding
    canvas_h = rows * cell + (rows + 1) * padding
    canvas = Image.new("RGB", (canvas_w, canvas_h), color="white")
    for idx, item in enumerate(selected):
        row = idx // cols
        col = idx % cols
        x = padding + col * (cell + padding)
        y = padding + row * (cell + padding)
        path = INPUT_IMAGES_DIR / item["filename"]
        if not path.exists():
            continue
        with Image.open(path) as img:
            thumb = img.convert("RGBA").copy()
            thumb.thumbnail((cell - 28, cell - 28), Image.Resampling.LANCZOS)
            rgb = Image.new("RGBA", (cell, cell), (255, 255, 255, 255))
            rgb.paste(thumb, (14 + (cell - thumb.width - 28) // 2, 14 + (cell - thumb.height - 28) // 2), thumb)
            canvas.paste(rgb.convert("RGB"), (x, y), rgb)
        reasons = ", ".join(item.get("rejection_reasons", [])[:2]) or "rejected"
        from PIL import ImageDraw

        draw = ImageDraw.Draw(canvas)
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(35, 35, 35), width=2)
        draw.text((x + 8, y + cell - 28), item["filename"], fill=(0, 0, 0))
        draw.text((x + 8, y + cell - 12), f"m={item['margin']:.3f}", fill=(0, 0, 0))
        draw.text((x + 8, y + 12), reasons[:18], fill=(120, 0, 0))
    canvas.save(output_path)


def build_accepted_preview(accepted: list[dict[str, Any]], output_path: Path) -> None:
    if not accepted:
        Image.new("RGB", (1200, 800), color=(245, 245, 245)).save(output_path)
        return

    selected = accepted[:100]
    cell = 170
    padding = 18
    cols = 10
    rows = (len(selected) + cols - 1) // cols
    canvas_w = cols * cell + (cols + 1) * padding
    canvas_h = rows * cell + (rows + 1) * padding
    canvas = Image.new("RGB", (canvas_w, canvas_h), color="white")
    for idx, item in enumerate(selected):
        row = idx // cols
        col = idx % cols
        x = padding + col * (cell + padding)
        y = padding + row * (cell + padding)
        path = INPUT_IMAGES_DIR / item["filename"]
        if not path.exists():
            continue
        with Image.open(path) as img:
            thumb = img.convert("RGBA").copy()
            thumb.thumbnail((cell - 28, cell - 28), Image.Resampling.LANCZOS)
            rgb = Image.new("RGBA", (cell, cell), (255, 255, 255, 255))
            rgb.paste(thumb, (14 + (cell - thumb.width - 28) // 2, 14 + (cell - thumb.height - 28) // 2), thumb)
            canvas.paste(rgb.convert("RGB"), (x, y), rgb)
        from PIL import ImageDraw

        draw = ImageDraw.Draw(canvas)
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(35, 35, 35), width=2)
        draw.text((x + 8, y + cell - 22), item["filename"], fill=(0, 0, 0))
    canvas.save(output_path)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    metadata_map = load_metadata_map(INPUT_METADATA_PATH)
    files = sorted(INPUT_IMAGES_DIR.glob("*.png"), key=lambda item: int(item.stem))

    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    rejection_reasons: dict[str, int] = {}
    caption_character_count = 0
    caption_non_character_count = 0
    caption_ambiguous_count = 0
    quality_rejected_count = 0
    caption_rejected_count = 0
    clip_rejected_count = 0

    for image_path in files:
        caption = metadata_map.get(image_path.name, "")
        caption_type = caption_classification(caption)
        if caption_type == "character":
            caption_character_count += 1
        elif caption_type == "non_character":
            caption_non_character_count += 1
        else:
            caption_ambiguous_count += 1

        try:
            with image_path.open("rb") as handle:
                image_bytes = handle.read()
        except OSError:
            rejected_records.append({
                "filename": image_path.name,
                "caption": caption,
                "character_confidence": 0.0,
                "non_character_confidence": 0.0,
                "margin": 0.0,
                "caption_classification": caption_type,
                "final_decision": False,
                "rejection_reasons": ["read_error"],
            })
            rejection_reasons["read_error"] = rejection_reasons.get("read_error", 0) + 1
            continue

        details = score_character_semantics(image_bytes, threshold=None)
        if not isinstance(details[2], dict):
            clip_details = {"character_confidence": 0.0, "non_character_confidence": 0.0, "margin": 0.0}
        else:
            clip_details = details[2]

        quality_ok = has_sufficient_content(image_bytes) and has_reasonable_character_composition(image_bytes)
        if not quality_ok:
            quality_rejected_count += 1
            rejection_reasons["quality_rejected"] = rejection_reasons.get("quality_rejected", 0) + 1

        decision = False
        reasons: list[str] = []

        if not quality_ok:
            reasons.append("quality_rejected")

        if caption_type == "non_character":
            reasons.append("caption_non_character")
            caption_rejected_count += 1
        elif not caption:
            reasons.append("missing_caption")
            caption_rejected_count += 1

        if float(clip_details.get("margin", 0.0)) < CLIP_THRESHOLD:
            reasons.append("clip_margin_below_threshold")
            clip_rejected_count += 1

        if caption_type == "character" and clip_details.get("margin", 0.0) >= CLIP_THRESHOLD and quality_ok:
            decision = True
        elif caption_type == "ambiguous" and clip_details.get("margin", 0.0) >= CLIP_THRESHOLD and quality_ok:
            decision = True

        if decision:
            accepted_records.append({
                "filename": image_path.name,
                "caption": caption,
                "character_confidence": float(clip_details.get("character_confidence", 0.0)),
                "non_character_confidence": float(clip_details.get("non_character_confidence", 0.0)),
                "margin": float(clip_details.get("margin", 0.0)),
                "caption_classification": caption_type,
                "final_decision": True,
                "rejection_reasons": [],
            })
            OUTPUT_IMAGES_DIR.joinpath(image_path.name).write_bytes(image_bytes)
            continue

        reasons = list(dict.fromkeys(reasons))
        for reason in reasons:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        rejected_records.append({
            "filename": image_path.name,
            "caption": caption,
            "character_confidence": float(clip_details.get("character_confidence", 0.0)),
            "non_character_confidence": float(clip_details.get("non_character_confidence", 0.0)),
            "margin": float(clip_details.get("margin", 0.0)),
            "caption_classification": caption_type,
            "final_decision": False,
            "rejection_reasons": reasons,
        })

    metadata_path = OUTPUT_METADATA_DIR / "metadata.jsonl"
    with metadata_path.open("w", encoding="utf-8") as handle:
        for record in accepted_records:
            handle.write(json.dumps({
                "file_name": f"images/{record['filename']}",
                "text": record["caption"],
            }, ensure_ascii=False) + "\n")

    report = {
        "input_count": len(files),
        "accepted_count": len(accepted_records),
        "rejected_count": len(rejected_records),
        "acceptance_rate": (len(accepted_records) / len(files)) if files else 0.0,
        "caption_character_count": caption_character_count,
        "caption_non_character_count": caption_non_character_count,
        "caption_ambiguous_count": caption_ambiguous_count,
        "clip_threshold": CLIP_THRESHOLD,
        "quality_rejected_count": quality_rejected_count,
        "caption_rejected_count": caption_rejected_count,
        "clip_rejected_count": clip_rejected_count,
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
    }

    report_path = OUTPUT_VALIDATION_DIR / "final_dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    preview_path = OUTPUT_VALIDATION_DIR / "final_dataset_preview.png"
    rejected_preview_path = OUTPUT_VALIDATION_DIR / "rejected_preview.png"
    build_accepted_preview(accepted_records, preview_path)
    build_rejected_preview(rejected_records, rejected_preview_path)

    print("Final dataset creation complete.")
    print(f"Input: {len(files)}")
    print(f"Accepted: {len(accepted_records)}")
    print(f"Rejected: {len(rejected_records)}")
    print(f"Acceptance rate: {report['acceptance_rate']:.4f}")
    print(f"Rejection reasons: {report['rejection_reasons']}")
    print(f"Report: {report_path}")
    print(f"Preview: {preview_path}")
    print(f"Rejected preview: {rejected_preview_path}")


if __name__ == "__main__":
    main()
