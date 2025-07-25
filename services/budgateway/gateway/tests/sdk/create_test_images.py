#!/usr/bin/env python3
"""
Create test images for image endpoint testing.
This script generates simple test images in various formats and sizes.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io


def create_test_image(size=(512, 512), format="PNG", text="Test Image", color=(100, 150, 200)):
    """Create a simple test image with text."""
    # Create a new image
    image = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(image)
    
    # Try to use a default font, fall back to default if not available
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except OSError:
            font = ImageFont.load_default()
    
    # Calculate text position to center it
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    # Add some geometric shapes for visual interest
    draw.rectangle([50, 50, 150, 150], outline=(255, 0, 0), width=3)
    draw.ellipse([size[0]-150, size[1]-150, size[0]-50, size[1]-50], 
                  outline=(0, 255, 0), width=3)
    
    return image


def create_mask_image(size=(512, 512)):
    """Create a mask image with transparent areas."""
    # Create a mask with transparent center
    mask = Image.new("RGBA", size, (0, 0, 0, 255))  # Black background
    draw = ImageDraw.Draw(mask)
    
    # Create transparent circle in center
    center_x, center_y = size[0] // 2, size[1] // 2
    radius = min(size) // 4
    draw.ellipse([center_x - radius, center_y - radius, 
                  center_x + radius, center_y + radius], 
                 fill=(0, 0, 0, 0))  # Transparent
    
    return mask


def main():
    """Create all test images."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "images"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    print("Creating test images...")
    
    # Create standard test image
    test_image = create_test_image(text="TensorZero Test")
    test_image.save(fixtures_dir / "test_image.png")
    print("✓ Created test_image.png")
    
    # Create smaller image for variation tests
    small_image = create_test_image(size=(256, 256), text="Small Test", color=(200, 100, 150))
    small_image.save(fixtures_dir / "small_test.png")
    print("✓ Created small_test.png")
    
    # Create larger image for editing tests
    large_image = create_test_image(size=(1024, 1024), text="Large Test", color=(150, 200, 100))
    large_image.save(fixtures_dir / "large_test.png")
    print("✓ Created large_test.png")
    
    # Create mask image for editing
    mask_image = create_mask_image()
    mask_image.save(fixtures_dir / "mask.png")
    print("✓ Created mask.png")
    
    # Create JPEG version for format testing
    jpeg_image = create_test_image(text="JPEG Test", color=(50, 100, 150))
    jpeg_image.save(fixtures_dir / "test_image.jpg", "JPEG", quality=90)
    print("✓ Created test_image.jpg")
    
    # Create images in different sizes for DALL-E testing
    sizes = [(256, 256), (512, 512), (1024, 1024), (1024, 1792), (1792, 1024)]
    for i, size in enumerate(sizes):
        img = create_test_image(
            size=size, 
            text=f"{size[0]}x{size[1]}", 
            color=(50 + i*30, 100 + i*20, 150 + i*10)
        )
        img.save(fixtures_dir / f"test_{size[0]}x{size[1]}.png")
        print(f"✓ Created test_{size[0]}x{size[1]}.png")
    
    # Create a very simple image for variation testing (DALL-E 2 works better with simpler images)
    simple_image = Image.new("RGB", (512, 512), (240, 240, 240))
    draw = ImageDraw.Draw(simple_image)
    draw.rectangle([200, 200, 312, 312], fill=(100, 100, 200))
    simple_image.save(fixtures_dir / "simple_shape.png")
    print("✓ Created simple_shape.png")
    
    print(f"\nAll test images created in: {fixtures_dir}")
    print("Images created:")
    for img_file in sorted(fixtures_dir.glob("*.png")) + sorted(fixtures_dir.glob("*.jpg")):
        size = Image.open(img_file).size
        print(f"  - {img_file.name}: {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()