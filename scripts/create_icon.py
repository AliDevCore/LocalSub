"""
Generate LocalSub application icon (PNG & ICO).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

assets_dir = Path(__file__).resolve().parent.parent / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)

size = (256, 256)
img = Image.new("RGBA", size, color=(0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Outer rounded rectangle (Dark Navy/Slate)
# (12, 12) to (244, 244)
draw.rounded_rectangle([12, 12, 244, 244], radius=48, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255), width=6)

# Inner accent wave / soundwave / subtitle lines
# Subtitle box
draw.rounded_rectangle([44, 64, 212, 140], radius=20, fill=(30, 41, 59, 255), outline=(2, 132, 199, 255), width=4)

# Subtitle text lines inside the TV / Screen
draw.rounded_rectangle([64, 86, 192, 98], radius=6, fill=(56, 189, 248, 255))
draw.rounded_rectangle([76, 110, 180, 122], radius=6, fill=(52, 211, 153, 255))

# Neural / AI Speech wave below
# 5 vertical sound bars
bars = [
    (68, 168, 80, 204),
    (92, 156, 104, 216),
    (116, 150, 128, 222),
    (140, 156, 152, 216),
    (164, 168, 176, 204),
    (188, 178, 200, 194),
]
for x1, y1, x2, y2 in bars:
    draw.rounded_rectangle([x1, y1, x2, y2], radius=6, fill=(56, 189, 248, 255))

# Save PNG
png_path = assets_dir / "app_icon.png"
img.save(str(png_path), format="PNG")

# Save ICO with multiple resolutions (16, 32, 48, 64, 128, 256)
ico_path = assets_dir / "app_icon.ico"
img.save(str(ico_path), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

print(f"Generated icons successfully:\n  PNG: {png_path}\n  ICO: {ico_path}")
