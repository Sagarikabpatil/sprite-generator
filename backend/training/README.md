# LoRA Training Scaffold

This directory contains the first lightweight LoRA fine-tuning setup for a 2D/pixel-art character model.

## Current status
- The dataset is prepared and copied into the final training-ready directory.
- Training is intentionally disabled by default.
- No large base model is downloaded automatically.
- This is a small first experiment intended for a local Windows workstation.

## Dataset used
- Input directory: ../data/character_curated_final/images
- Metadata: ../data/character_curated_final/metadata/metadata.jsonl

## Recommended base model
- runwayml/stable-diffusion-v1-5

This is a standard Stable Diffusion base suitable for a compact character LoRA experiment on a local Windows machine without forcing a large multi-GPU setup.

## Minimal first experiment settings
- Resolution: 512
- Batch size: 1
- Gradient accumulation: 4
- Learning rate: 1e-4
- Epochs: 1
- LoRA rank: 8
- LoRA alpha: 16
- Output directory: ../data/lora_output/first_experiment
- Checkpoint interval: every 100 steps

## Safety
- The script defaults to verification-only mode.
- It will report dataset integrity, image dimensions, captions, and GPU availability.
- It will not start training until an explicit training command is used.

## Verification command
python training/verify_training_setup.py

## Training command (when ready)
python training/train_lora.py --config training/config.yaml --train
