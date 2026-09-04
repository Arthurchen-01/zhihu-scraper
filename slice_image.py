from PIL import Image
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

img_path = Path(r"C:/Users/25472/.gemini/antigravity/brain/96353930-0ede-48a8-be01-ea896847ab4c/.user_uploaded/media_1787643703811.jpg")

if img_path.exists():
    img = Image.open(img_path)
    print(f"Image format: {img.format}, size: {img.size}, mode: {img.mode}")
    # Slice the image into 4 vertical segments to inspect clearly
    w, h = img.size
    slices = 5
    slice_h = h // slices
    out_dir = Path("outputs/image_slices")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(slices):
        box = (0, i * slice_h, w, min(h, (i + 1) * slice_h))
        cropped = img.crop(box)
        crop_path = out_dir / f"slice_{i+1}.png"
        cropped.save(crop_path)
        print(f"Saved slice {i+1}: {crop_path} (box: {box})")
else:
    print("Image not found")
