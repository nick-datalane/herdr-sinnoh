# Sinnoh-era Pokémon: the Pokémon Platinum front sprites (80×80, DS era) from art/sprites-gen4/<game>/<dex>.png,
# downloaded from the PokeAPI/sprites repository, with English names in art/sprites-gen4/names.json.
# frames(dex) → {pose: RGBA uint8 array}, each cropped to the sprite with the feet on the bottom row:
#   idle / walk / wave / smash (agent working) = the sprite exactly as the game draws it; while working the
#       city floats music notes over its head instead of changing the pose
#   roar (agent done) = the sprite with sparkles around its head
# face(arr, size) → size×size "photo" of the face region, for roster cards, pane headers and the news card.
# Standalone: python3 art/gen4.py <out.png> [dex ...]  → contact sheet of poses and crops at 2×
import json, os, sys
import numpy as np
from PIL import Image

ART = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ART, "sprites-gen4")
GAMES = ("platinum", "diamond-pearl")        # first one found wins
POSES = ("idle", "walk", "smash", "roar", "wave")
SPARK = np.array([255, 230, 109, 255], dtype=np.uint8)
SPARK_CORE = np.array([255, 255, 255, 255], dtype=np.uint8)

_names = None


def name(dex):
    global _names
    if _names is None:
        with open(os.path.join(SRC, "names.json"), encoding="utf-8") as f:
            _names = json.load(f)
    return _names[str(dex)]


def load(dex):
    for game in GAMES:
        p = os.path.join(SRC, game, f"{dex}.png")
        if os.path.exists(p):
            a = np.asarray(Image.open(p).convert("RGBA")).copy()
            # hard pixel edges: no half-transparent pixels
            a[a[:, :, 3] < 128] = 0
            a[a[:, :, 3] >= 128, 3] = 255
            ys, xs = np.where(a[:, :, 3] > 0)
            assert len(xs), f"{p}: empty sprite"
            return np.ascontiguousarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    raise FileNotFoundError(f"no sprite for #{dex} in {SRC}")


def star(out, free, x, y, r):
    # plus-shaped sparkle drawn only over empty pixels
    h, w = out.shape[:2]
    for d in range(-r, r + 1):
        for px, py in ((x + d, y), (x, y + d)):
            if 0 <= px < w and 0 <= py < h and free[py, px]:
                out[py, px] = SPARK
    if 0 <= x < w and 0 <= y < h and free[y, x]:
        out[y, x] = SPARK_CORE


def cheer(arr):
    # sparkles left, right and above the head; the frame grows sideways and upwards, never downwards
    pad, top = 7, 8
    h, w = arr.shape[:2]
    out = np.zeros((h + top, w + 2 * pad, 4), dtype=np.uint8)
    out[top:, pad:pad + w] = arr
    free = out[:, :, 3] == 0
    pts = [
        (pad - 4, top + h // 5, 2),
        (pad + w + 3, top + h // 8, 2),
        (pad + w // 3, 2, 1),
        (pad + w * 3 // 4, 4, 2),
        (pad - 2, top + h // 2, 1),
        (pad + w + 1, top + h * 2 // 5, 1),
    ]
    for x, y, r in pts:
        star(out, free, x, y, r)
    return out


def frames(dex):
    base = load(dex)
    return {"idle": base, "walk": base, "wave": base, "smash": base, "roar": cheer(base)}


def face(arr, size):
    # size×size window around the face: the centre of the opaque pixels in the top 45 % of the sprite,
    # kept inside the sprite; a sprite smaller than the window is centred in it
    h, w = arr.shape[:2]
    top = arr[:max(1, round(h * 0.45))]
    ys, xs = np.where(top[:, :, 3] > 0)
    cx, cy = (xs.mean(), ys.mean()) if len(xs) else (w / 2, h / 4)
    left = (w - size) // 2 if w <= size else min(max(int(round(cx - size / 2)), 0), w - size)
    topy = (h - size) // 2 if h <= size else min(max(int(round(cy - size * 0.45)), 0), h - size)
    box = np.zeros((size, size, 4), dtype=np.uint8)
    sx0, sy0 = max(left, 0), max(topy, 0)
    sx1, sy1 = min(left + size, w), min(topy + size, h)
    box[sy0 - topy:sy1 - topy, sx0 - left:sx1 - left] = arr[sy0:sy1, sx0:sx1]
    return box


def main(out, dexes):
    cell, k = 100, 2
    rows = []
    for dex in dexes:
        fr = frames(dex)
        row = Image.new("RGBA", (cell * 7, cell), (245, 245, 244, 255))
        for i, pose in enumerate(POSES):
            im = Image.fromarray(fr[pose], "RGBA")
            row.alpha_composite(im, ((cell - im.width) // 2 + i * cell, cell - 6 - im.height))
        for i, size in enumerate((48, 32)):
            im = Image.fromarray(face(fr["idle"], size), "RGBA")
            row.alpha_composite(im, ((cell - size) // 2 + (5 + i) * cell, (cell - size) // 2))
        rows.append(row)
    sheet = Image.new("RGBA", (cell * 7, cell * len(rows)), (245, 245, 244, 255))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * cell))
    sheet.resize((sheet.width * k, sheet.height * k), Image.NEAREST).save(out)


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2:]] or [25, 143, 130, 399, 448, 393, 94, 95])
