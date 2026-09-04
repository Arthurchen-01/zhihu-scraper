from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

img_path = Path(r"C:/Users/25472/.gemini/antigravity/brain/96353930-0ede-48a8-be01-ea896847ab4c/.user_uploaded/media_1787643703811.jpg")
img = Image.open(img_path)

# Enlarge 4x with high quality Lanczos filter and sharpen
w, h = img.size
enlarged = img.resize((w * 6, h * 6), Image.Resampling.LANCZOS)
enhancer = ImageEnhance.Contrast(enlarged)
contrasted = enhancer.enhance(1.8)
sharpened = contrasted.filter(ImageFilter.SHARPEN)

out_dir = Path("outputs/enhanced_slices")
out_dir.mkdir(parents=True, exist_ok=True)

slices = 10
sh = sharpened.height // slices
for i in range(slices):
    box = (0, i * sh, sharpened.width, min(sharpened.height, (i + 1) * sh))
    crop = sharpened.crop(box)
    crop.save(out_dir / f"part_{i+1}.png")
    print(f"Saved part {i+1}")
