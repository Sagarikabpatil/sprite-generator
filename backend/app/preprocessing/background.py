"""Background processing utilities for sprite preparation.

This module is responsible for isolating foreground subjects from their
backgrounds and preparing images for downstream sprite generation tasks.
"""

from __future__ import annotations

from rembg import remove


def remove_background(input_path: str, output_path: str) -> None:
    """Remove the background from an image file and save the result.

    This function reads an image from disk, applies the rembg background removal
    pipeline, and writes the resulting transparent PNG to the specified output
    location.

    Args:
        input_path (str): The filesystem path to the source image.
        output_path (str): The filesystem path where the processed image will be
            saved.
    """
    with open(input_path, "rb") as input_file:
        input_data = input_file.read()

    output_data = remove(input_data)

    with open(output_path, "wb") as output_file:
        output_file.write(output_data)
