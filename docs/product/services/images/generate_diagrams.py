#!/usr/bin/env python3
"""Generate PNG diagrams from Mermaid files using kroki.io API with white background."""

import base64
import zlib
from pathlib import Path
import urllib.request
import urllib.error
from io import BytesIO

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def encode_kroki(diagram: str) -> str:
    """Encode diagram for kroki.io URL."""
    compressed = zlib.compress(diagram.encode("utf-8"), 9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def add_white_background(png_data: bytes) -> bytes:
    """Add white background to PNG image using PIL."""
    if not HAS_PIL:
        return png_data

    # Open the image
    img = Image.open(BytesIO(png_data))

    # If image has alpha channel, composite with white background
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        # Create white background
        background = Image.new("RGB", img.size, (255, 255, 255))

        # Convert to RGBA if needed
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Composite the image onto the white background
        background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Save to bytes
    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def generate_png(mmd_file: Path, output_file: Path):
    """Generate PNG from mermaid file using kroki.io."""
    diagram = mmd_file.read_text()
    encoded = encode_kroki(diagram)

    url = f"https://kroki.io/mermaid/png/{encoded}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            png_data = response.read()

            # Add white background
            png_data = add_white_background(png_data)

            output_file.write_bytes(png_data)
            print(f"Generated: {output_file.name}")
    except urllib.error.URLError as e:
        print(f"Error generating {output_file.name}: {e}")
        return False
    return True


def main():
    if not HAS_PIL:
        print("Warning: PIL/Pillow not installed. Installing...")
        import subprocess

        subprocess.run(["pip", "install", "Pillow"], check=True)
        print("Please run the script again.")
        return

    images_dir = Path(__file__).parent

    # Find all .mmd files
    mmd_files = list(images_dir.glob("*.mmd"))

    if not mmd_files:
        print("No .mmd files found")
        return

    for mmd_path in mmd_files:
        png_path = mmd_path.with_suffix(".png")
        generate_png(mmd_path, png_path)


if __name__ == "__main__":
    main()
