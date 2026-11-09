"""Render original Chagatai UI art at the native Garrison surface sizes."""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZES = {
    "flag_list": (104, 56), "flag_list_small": (52, 28),
    "flag_secondary": (440, 248), "flag_secondary_small": (220, 124),
    "flag_fade": (344, 104), "flag_loading": (1920, 1080),
    "flag_background": (1920, 1080), "flag_pattern": (1120, 352),
    "flag_tile": (736, 800), "flag_mastery": (1112, 588),
}

def banner():
    width, height = 1200, 680
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    rng = random.Random(401)
    for y in range(height):
        for x in range(width):
            weave = (x % 3 - 1) * 1.3 + (y % 4 - 1.5) * 0.9
            fold = 10 * math.sin(x / 87 + y / 204) + 4 * math.sin(x / 29 + y / 160)
            light = weave + fold + rng.uniform(-5, 5)
            pixels[x, y] = tuple(round(c + light) for c in (31, 75, 71))
    draw = ImageDraw.Draw(image)
    for inset, color, weight in [(12, "#9b7b49", 7), (23, "#cfa45e", 3), (39, "#547e66", 3)]:
        draw.rectangle((inset, inset, width-inset-1, height-inset-1), outline=color, width=weight)
    for x in range(64, width-63, 28):
        for y in (53, height-53):
            draw.polygon([(x-8,y),(x,y-5),(x+8,y),(x,y+5)], fill="#b28a51")
    cx, cy = width // 2, height // 2
    # Chaghatayid tamgha, Fedorov, ONS Newsletter 162, fig. 1.7.
    # The textile and coin border are original UI treatments.
    draw.ellipse((cx-143,cy-143,cx+143,cy+143),outline="#c59c58",width=5)
    draw.ellipse((cx-88,cy-94,cx+88,cy+23),outline="#edcb89",width=17)
    draw.line((cx,cy-100,cx,cy+101),fill="#edcb89",width=17)
    draw.line((cx-32,cy+97,cx+32,cy+97),fill="#edcb89",width=13)
    return image

def render(target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    master = banner()
    master.save(target/"cover.png")
    for name, size in SIZES.items():
        # Crop the small badges around the mark. Keep the full cloth for banners.
        art = master
        if name in {"flag_list", "flag_list_small", "flag_secondary_small"}:
            art = master.crop((240,145,960,535))
        elif name == "flag_tile":
            art = master.crop((295,8,905,672))
        image = art.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
        if name in {"flag_loading", "flag_background", "flag_fade", "flag_pattern"}:
            width, height = size
            curve = [round(239 * (1 - x / max(1, width-1))**1.8) for x in range(width)]
            alpha = Image.new("L", (width, 1))
            alpha.putdata(curve)
            alpha = alpha.resize(size)
            if name in {"flag_fade", "flag_pattern"}:
                image.putalpha(alpha.point(lambda value: 255-value))
            else:
                shade = Image.new("RGBA", size, (8, 16, 18))
                shade.putalpha(alpha)
                image = Image.alpha_composite(image.filter(ImageFilter.GaussianBlur(0.4)), shade)
        image.save(target/(name+".png"))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    render(parser.parse_args().output)
