"""Calibrate CLIP-based semantic scores for the character_clean dataset without creating a curated dataset yet."""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.datasets.semantic_filter import score_character_semantics

INPUT_IMAGES_DIR = BASE_DIR / "data" / "character_clean" / "images"
OUTPUT_DIR = BASE_DIR / "data" / "character_curated" / "validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def select_preview(files: list[Path], count: int, mode: str) -> list[Path]:
    if len(files) <= count:
        return files
    if mode == "top":
        ranked = sorted(files, key=lambda p: compute_score(p), reverse=True)
    elif mode == "middle":
        ranked = sorted(files, key=lambda p: abs(compute_score(p) - 0.5))
    else:
        ranked = sorted(files, key=lambda p: compute_score(p))
    return ranked[:count]


def compute_score(path: Path) -> float:
    with path.open("rb") as handle:
        image_bytes = handle.read()
    character_confidence, _accepted, details = score_character_semantics(
        image_bytes,
        threshold=None,
        character_min_confidence=0.55,
        character_margin=0.05,
    )
    if isinstance(details, dict):
        return float(details.get("character_confidence", 0.0))
    return float(character_confidence)


def main() -> None:
    files = sorted(INPUT_IMAGES_DIR.glob("*.png"), key=lambda p: int(p.stem))
    all_records = []
    margins = []
    character_confidences = []
    non_character_confidences = []

    for path in files:
        with path.open("rb") as handle:
            image_bytes = handle.read()

        character_confidence, _accepted, details = score_character_semantics(
            image_bytes,
            threshold=None,
            character_min_confidence=0.55,
            character_margin=0.05,
        )
        if not isinstance(details, dict):
            continue

        character_value = float(details.get("character_confidence", 0.0))
        non_character_value = float(details.get("non_character_confidence", 0.0))
        margin_value = float(details.get("margin", 0.0))

        all_records.append({
            "filename": path.name,
            "character_confidence": character_value,
            "non_character_confidence": non_character_value,
            "margin": margin_value,
        })
        character_confidences.append(character_value)
        non_character_confidences.append(non_character_value)
        margins.append(margin_value)

    summary = {
        "count": len(all_records),
        "character_confidence": {
            "min": min(character_confidences) if character_confidences else 0.0,
            "max": max(character_confidences) if character_confidences else 0.0,
            "mean": float(statistics.fmean(character_confidences)) if character_confidences else 0.0,
            "median": float(statistics.median(character_confidences)) if character_confidences else 0.0,
            "p75": percentile(character_confidences, 0.75),
            "p90": percentile(character_confidences, 0.90),
            "p95": percentile(character_confidences, 0.95),
            "p99": percentile(character_confidences, 0.99),
        },
        "non_character_confidence": {
            "min": min(non_character_confidences) if non_character_confidences else 0.0,
            "max": max(non_character_confidences) if non_character_confidences else 0.0,
            "mean": float(statistics.fmean(non_character_confidences)) if non_character_confidences else 0.0,
            "median": float(statistics.median(non_character_confidences)) if non_character_confidences else 0.0,
            "p75": percentile(non_character_confidences, 0.75),
            "p90": percentile(non_character_confidences, 0.90),
            "p95": percentile(non_character_confidences, 0.95),
            "p99": percentile(non_character_confidences, 0.99),
        },
        "margin": {
            "min": min(margins) if margins else 0.0,
            "max": max(margins) if margins else 0.0,
            "mean": float(statistics.fmean(margins)) if margins else 0.0,
            "median": float(statistics.median(margins)) if margins else 0.0,
            "p75": percentile(margins, 0.75),
            "p90": percentile(margins, 0.90),
            "p95": percentile(margins, 0.95),
            "p99": percentile(margins, 0.99),
        },
        "minimum_margin": min(margins) if margins else 0.0,
        "median_margin": float(statistics.median(margins)) if margins else 0.0,
        "p75_margin": percentile(margins, 0.75),
        "p90_margin": percentile(margins, 0.90),
        "p95_margin": percentile(margins, 0.95),
    }

    top_20 = sorted(all_records, key=lambda item: item["margin"], reverse=True)[:20]
    bottom_20 = sorted(all_records, key=lambda item: item["margin"])[:20]

    report = {
        "summary": summary,
        "top_20_by_margin": top_20,
        "bottom_20_by_margin": bottom_20,
        "all_records": all_records,
    }

    report_path = OUTPUT_DIR / "semantic_calibration.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("TOP_20_MARGIN")
    for item in top_20:
        print(f"{item['filename']} | margin={item['margin']:.6f} | character={item['character_confidence']:.6f} | non_character={item['non_character_confidence']:.6f}")
    print("BOTTOM_20_MARGIN")
    for item in bottom_20:
        print(f"{item['filename']} | margin={item['margin']:.6f} | character={item['character_confidence']:.6f} | non_character={item['non_character_confidence']:.6f}")
    print(f"report_path={report_path}")


if __name__ == "__main__":
    main()
