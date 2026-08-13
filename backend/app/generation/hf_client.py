"""
hf_client.py

Handles communication with Hugging Face Inference API.

Responsibilities:
- Load Hugging Face token
- Send prompt to the model
- Receive generated image
"""

import io
import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from PIL import Image

# Load environment variables
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise ValueError(
        "HF_TOKEN not found. Please add it to backend/.env"
    )

# Create Hugging Face client
client = InferenceClient(
    provider="hf-inference",
    api_key=HF_TOKEN,
)


def generate_image(prompt: str) -> Image.Image:
    """
    Generates an image from a text prompt using Hugging Face.

    Args:
        prompt (str): User prompt.

    Returns:
        PIL.Image.Image: Generated image.
    """

    image = client.text_to_image(
        prompt,
        model="stabilityai/sdxl-turbo",
    )

    return image