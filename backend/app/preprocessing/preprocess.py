"""Character preprocessing utilities for sprite preparation.

This module contains the image preprocessing steps used to normalize uploaded
character assets before they are stored for downstream sprite generation.
"""

from __future__ import annotations


def preprocess_character(
    input_path: str,
    output_path: str,
    canvas_size: tuple[int, int] = (256, 256),
) -> None:
    """Prepare a character image for sprite generation and save the result.

    The function opens an RGBA image, removes transparent borders, resizes the
    image while preserving aspect ratio, places it on a transparent canvas,
    centers it horizontally, aligns it near the bottom, and writes the output
    image to disk.

    Args:
        input_path (str): The filesystem path to the source image.
        output_path (str): The destination path for the processed image.
        canvas_size (tuple[int, int]): The target canvas dimensions used for
            final placement. Defaults to (256, 256).
    """
    from PIL import Image

    image = Image.open(input_path).convert("RGBA")

    # Crop transparent borders
    bbox = image.getbbox()

    if bbox:
        image = image.crop(bbox)

    # Resize while keeping aspect ratio
    max_size = 220
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Create transparent canvas
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    # Center horizontally
    x = (canvas_size[0] - image.width) // 2

    # Align feet near bottom
    bottom_margin = 10
    y = canvas_size[1] - image.height - bottom_margin

    canvas.paste(image, (x, y), image)

    canvas.save(output_path)
