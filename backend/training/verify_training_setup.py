"""Verify the LoRA training environment and dataset before any actual training run."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATASET_DIR = BASE_DIR / "data" / "character_curated_final"
IMAGE_DIR = DATASET_DIR / "images"
METADATA_PATH = DATASET_DIR / "metadata" / "metadata.jsonl"
OUTPUT_DIR = BASE_DIR / "data" / "lora_output" / "first_experiment"


def check_gpu() -> dict:
    info = {
        "cuda_available": False,
        "gpu_name": None,
        "vram_detected_mb": None,
    }
    try:
        import torch

        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            if torch.cuda.is_available():
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                info["vram_detected_mb"] = round((total_bytes / (1024 ** 2)), 2)
    except Exception:
        info["cuda_available"] = False
    return info


def load_metadata() -> list[dict]:
    if not METADATA_PATH.exists():
        return []
    entries = []
    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def verify_dataset() -> dict:
    summary = {
        "image_count": 0,
        "caption_count": 0,
        "image_dimensions": {},
        "dimension_samples": [],
        "missing_captions": 0,
    }
    if not IMAGE_DIR.exists():
        return summary

    image_files = sorted(IMAGE_DIR.glob("*.png"), key=lambda p: int(p.stem))
    metadata = load_metadata()
    metadata_by_name = {item.get("file_name", "").split("/")[-1]: item.get("text", "") for item in metadata}

    widths = []
    heights = []
    for image_path in image_files:
        try:
            with Image.open(image_path) as image:
                image.verify()
                with Image.open(image_path) as image2:
                    width, height = image2.size
                    widths.append(width)
                    heights.append(height)
                    if width != 512 or height != 512:
                        summary["dimension_samples"].append({
                            "filename": image_path.name,
                            "width": width,
                            "height": height,
                        })
        except Exception:
            continue

    summary["image_count"] = len(image_files)
    summary["caption_count"] = len(metadata)
    summary["missing_captions"] = len([path for path in image_files if path.name not in metadata_by_name or not metadata_by_name[path.name]])
    if widths and heights:
        summary["image_dimensions"] = {
            "min_width": min(widths),
            "max_width": max(widths),
            "min_height": min(heights),
            "max_height": max(heights),
            "unique_widths": sorted(set(widths)),
            "unique_heights": sorted(set(heights)),
        }
    return summary


def main() -> None:
    print("Verifying LoRA training setup...")
    gpu = check_gpu()
    dataset = verify_dataset()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("GPU availability:")
    print(json.dumps(gpu, indent=2, ensure_ascii=False))
    print("Dataset summary:")
    print(json.dumps(dataset, indent=2, ensure_ascii=False))
    print("Output directory:")
    print(str(OUTPUT_DIR))
    print("Required packages:")
    print("- torch")
    print("- diffusers")
    print("- transformers")
    print("- accelerate")
    print("- peft")
    print("- pillow")
    print("- pyyaml")
    print("- datasets")
    print("Base model:")
    print("runwayml/stable-diffusion-v1-5")
    print("Estimated training requirements:")
    print("- Small first experiment only")
    print("- 512x512 resolution")
    print("- 1 epoch / ~250 steps target")
    print("- 1 GPU or CPU fallback (not started in this session)")
    print("Training command (verification only):")
    print("python training/train_lora.py --config training/config.yaml --train")


if __name__ == "__main__":
    main()
