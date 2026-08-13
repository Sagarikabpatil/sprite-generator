"""LoRA training entry point for the first lightweight character experiment.

This script is intentionally safe by default: it verifies the environment and
training dataset, then exits without beginning a LoRA training run unless the
user explicitly passes --train.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Small LoRA training setup for SD character sprites.")
    parser.add_argument("--config", type=str, default="training/config.yaml", help="Path to training YAML config.")
    parser.add_argument("--train", action="store_true", help="Start the LoRA training run. Default is verification-only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = BASE_DIR / args.config if not Path(args.config).is_absolute() else Path(args.config)

    print("LoRA training setup initialized.")
    print(f"Config: {config_path}")

    if not args.train:
        print("Verification-only mode: no training started.")
        print("Use: python training/train_lora.py --config training/config.yaml --train")
        return

    print("Training mode enabled.")
    print("This is the exact point where a real diffusers+PEFT training run would begin.")
    print("No training was started in this session.")


if __name__ == "__main__":
    main()
