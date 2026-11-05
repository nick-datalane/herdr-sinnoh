# Animated scenes: the water drifts and the flowers sway, as the DS does it. For every place in art/places.json
# this builds <id>.gif: the same crop as the static scene, the same 2x nearest-neighbour scaling, the same daylight
# art, so the GIF stands in for the PNG. build_assets.py calls build() to put them in the mod's assets; run on its
# own, this writes art/animated/ with a preview.html for a look in a browser. Water is found by colour (per
# place), its texture scrolls down inside the water mask by one map pixel per frame and wraps over the tile period
# of the texture, so the loop is seamless. Blooms are found as small bright patches on grass and shift one pixel
# left and right. Places with nothing to animate get no GIF.
#   python3 art/animate.py            all places
#   python3 art/animate.py acuity     one place
#   python3 art/animate.py --masks    write the mask review sheet (art/animated/masks.png) and stop
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

ART = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ART, "animated")
FRAME_MS = 120          # water: one map pixel per frame
SWAY = [0, 1, 0, -1]    # the bloom offsets in map pixels, cycled; each state holds a quarter of the loop
PERIODS = [8, 12, 16, 20, 24, 32]   # the vertical repeats a DS water texture can have (lakes 24, sea 12, falls 20)
MAX_FRAMES = 16         # Herdr keeps every decoded frame of a shown GIF (about 8 MB each at 2x), so loops stay short
LOOPS = [4, 6, 8, 10, 12, 15, 16]   # loop lengths to pick from
FLOWER_FRAMES = 16      # a place with flowers and no water (4 sway states; identical frames merge in the file)

# per place: how to find the water (b minus r, b minus g, minimum b), rectangles [x, y, w, h] that cut a body
# with its own texture (a waterfall) out of the water, and whether to sway the blooms
ANIM = {
    "verity":      {"water": (60, 20, 120)},
    "acuity":      {"water": (60, 20, 120)},
    "floaroma":    {"flowers": True},
    "eterna":      {},
    "sunyshore":   {"water": (70, 30, 140)},
    "snowpoint":   {},
    "valor-beach": {"water": (70, 25, 130)},
    # the waterfall is cut out of the pool above it, so each scrolls with its own texture
    "league":      {"water": (50, 15, 120), "split": [[111, 229, 176, 142]]},
    "resort":      {"water": (60, 20, 120)},
    "paradise":    {"water": (60, 20, 120), "flowers": True},
    "twinleaf":    {"water": (60, 20, 120)},
    "hearthome":   {},   # the fountain bowls are too small: scrolling them only smears the rim shading
}
MIN_WATER_PX = 300      # drop blue specks (signs, roofs, pokéballs) smaller than this, in map pixels
MAX_BLOOM_PX = 120      # a bloom cluster is small; roofs, fences, paths and people are bigger or longer
MAX_BLOOM_H = 16
MAX_BLOOM_W = 48

def load(p):
    x, y, w, h = p["crop"]
    full = Image.open(os.path.join(ART, "maps-gen4", p["map"])).convert("RGB")
    return np.asarray(full.crop((x, y, x + w, y + h))).astype(np.int16)

def water_mask(a, cfg):
    br, bg, bmin = cfg
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (b - r > br) & (b - g > bg) & (b > bmin)
    m = ndimage.binary_closing(m, iterations=1)
    lab, n = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= MIN_WATER_PX
    return keep[lab]

def is_grass(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g > r + 20) & (g > b + 20) & (g > 90)

def bloom_mask(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    petal = (mx > 165) & (sat > 0.28) & ~is_grass(a)        # a bright, colourful pixel that isn't grass
    white = (mn > 200)                                      # the white hearts of the blooms
    cand = petal | white
    lab, n = ndimage.label(cand, structure=np.ones((3, 3)))
    if n == 0:
        return cand
    sizes = ndimage.sum(cand, lab, range(1, n + 1))
    boxes = ndimage.find_objects(lab)
    keep = np.zeros(n + 1, bool)
    for i, (sl, sz) in enumerate(zip(boxes, sizes), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        keep[i] = sz <= MAX_BLOOM_PX and h <= MAX_BLOOM_H and w <= MAX_BLOOM_W
    small = keep[lab]
    # in a bed: a fair share of the 9x9 around it is grass or leaves
    around = ndimage.uniform_filter(is_grass(a).astype(float), 9)
    return small & (around > 0.25)

def near(a, b, tol=40):
    return np.abs(a - b).max(-1) < tol

def bodies(a, m, split=()):
    """Each body of water with its own texture period: the smallest repeat in PERIODS whose colours agree
    inside the body, unless a longer one agrees clearly better (a lake's diagonal waves repeat every 24).
    `split` rectangles cut bodies of their own out of the mask. Pixels that don't repeat at the period (a
    waterfall's crest, foam along a shore) are kept still, so the scroll never drags them along."""
    pieces = []
    rest = m.copy()
    for x, y, w, h in split:
        cut = np.zeros_like(m); cut[y:y + h, x:x + w] = True
        pieces.append(m & cut); rest &= ~cut
    pieces.append(rest)
    out = []
    for piece in pieces:
        lab, n = ndimage.label(piece)
        for i in range(1, n + 1):
            cm = lab == i
            if cm.sum() < MIN_WATER_PX:
                continue
            inner = ndimage.binary_erosion(cm, iterations=2)
            best, score = PERIODS[0], -1.0
            for P in PERIODS:
                src = inner[P:] & inner[:-P]
                if src.sum() < 200:
                    continue
                sc = near(a[P:], a[:-P])[src].mean()
                if sc > score + 0.03:
                    best, score = P, sc
            P = best
            # flat water (a pond: one colour with a shaded rim) has nothing to scroll; moving it only drags the rim
            interior = ndimage.binary_erosion(cm, iterations=3)
            if interior.sum() >= 100:
                q = (a[interior] // 8).astype(np.int32)
                _, inv, cnt = np.unique(q, axis=0, return_inverse=True, return_counts=True)
                base = a[interior][inv == int(np.argmax(cnt))].mean(0)
                if near(a[interior], base, 14).mean() > 0.92:
                    continue
            # a pixel moves when the one a period below or above it is the same colour (and in the body)
            down = np.zeros_like(cm); down[:-P] = cm[P:] & near(a[:-P], a[P:])
            up = np.zeros_like(cm); up[P:] = cm[:-P] & near(a[P:], a[:-P])
            still = cm & ~(down | up)
            still = ndimage.binary_opening(still, structure=np.ones((3, 3)))   # not lone noisy pixels
            out.append(dict(mask=cm & ~still, size=int(cm.sum()), period=P, score=score, still=int(still.sum())))
    out.sort(key=lambda b: -b["size"])
    return out

def loop_length(bod):
    """The loop length and each body's step (px per frame). First choice: the shortest loop of at most MAX_FRAMES
    where every body comes back to its start at 1 px per frame, then at 1 or 2 px per frame. If none exists (a waterfall repeating every
    20 next to pools repeating every 12), the biggest body closes and the others step 1 px and jump a little at
    the loop; the loop with the smallest total jump wins."""
    for allowed in ((1,), (1, 2)):   # 1 px per frame whenever a loop that short exists; 2 px only when it must
        for n in LOOPS:
            speeds = [next((s for s in allowed if (n * s) % b["period"] == 0), None) for b in bod]
            if None not in speeds:
                return n, speeds
    best = None
    for n in LOOPS:
        s0 = next((s for s in (1, 2) if (n * s) % bod[0]["period"] == 0), None)
        if s0 is None:
            continue
        jump = sum(min(n % b["period"], b["period"] - n % b["period"]) for b in bod[1:])
        if best is None or jump < best[0]:
            best = (jump, n, [s0] + [1] * (len(bod) - 1))
    if best:
        return best[1], best[2]
    return MAX_FRAMES, [1] * len(bod)

def scroll_body(out, a, m, k, P):
    """Every pixel of the body takes the colour of the one k rows up, wrapped over the period P."""
    h = a.shape[0]
    ys, xs = np.nonzero(m)
    src = ys - (k % P)
    # a source outside the body: the same spot one period down, then two, then the pixel itself
    for _ in range(3):
        bad = (src < 0) | ~m[np.clip(src, 0, h - 1), xs]
        if not bad.any():
            break
        src = np.where(bad, src + P, src)
    bad = (src < 0) | (src >= h) | ~m[np.clip(src, 0, h - 1), xs]
    src = np.where(bad, ys, src)
    out[ys, xs] = a[src, xs]

def ground_fill(a, blooms):
    """The grass under the blooms: each bloom pixel takes the nearest non-bloom pixel's colour."""
    idx = ndimage.distance_transform_edt(blooms, return_distances=False, return_indices=True)
    return a[idx[0], idx[1]]

def sway_flowers(a, blooms, ground, dx):
    if dx == 0:
        return a
    out = a.copy()
    out[blooms] = ground[blooms]
    ys, xs = np.nonzero(blooms)
    nx = xs + dx
    ok = (nx >= 0) & (nx < a.shape[1])
    ys, xs, nx = ys[ok], xs[ok], nx[ok]
    # land only on grass or on another bloom, never on a path or a wall
    land = blooms[ys, nx] | is_grass(a)[ys, nx]
    out[ys[land], nx[land]] = a[ys[land], xs[land]]
    return out

def to2x(arr):
    return Image.fromarray(arr.astype(np.uint8)).resize((arr.shape[1] * 2, arr.shape[0] * 2), Image.NEAREST)

def build(p, cfg, out=OUT):
    a = load(p)
    w = water_mask(a, cfg["water"]) if cfg.get("water") else None
    fl = bloom_mask(a) if cfg.get("flowers") else None
    if w is not None and w.sum() < MIN_WATER_PX:
        w = None
    if fl is not None and fl.sum() < 20:
        fl = None
    if w is None and fl is None:
        return None
    bod = bodies(a, w, cfg.get("split", ())) if w is not None else []
    if not bod and fl is None:
        return None
    if bod:
        n, speeds = loop_length(bod)
    else:
        n, speeds = FLOWER_FRAMES, []
    ms = FRAME_MS + 30 if 2 in speeds else FRAME_MS   # bodies at 2 px per frame get a little longer per frame
    hold = max(1, n // len(SWAY))
    ground = ground_fill(a, fl) if fl is not None else None
    frames = []
    for k in range(n):
        f = a.copy()
        for b, sp in zip(bod, speeds):
            scroll_body(f, a, b["mask"], k * sp, b["period"])
        if fl is not None:
            f = sway_flowers(f, fl, ground, SWAY[(k // hold) % len(SWAY)])
        frames.append(to2x(f))
    # one palette for every frame (scrolling and swaying add no colours), no dither: pixel art stays crisp
    pal = frames[0].quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{p['id']}.gif")
    q[0].save(path, save_all=True, append_images=q[1:], loop=0, duration=ms, disposal=1, optimize=False)
    return dict(path=path, frames=n, ms=ms, water=int(w.sum()) if w is not None else 0,
                bodies=[(b["size"], b["period"], sp, round(b["score"], 2), b["still"]) for b, sp in zip(bod[:4], speeds)],
                blooms=int(fl.sum()) if fl is not None else 0, bytes=os.path.getsize(path))

def mask_sheet(places):
    W, H, cols = 400, 480, 4
    sheet = Image.new("RGB", (cols * W, 3 * H), (30, 30, 30))
    for i, p in enumerate(places):
        a = load(p)
        cfg = ANIM.get(p["id"], {})
        show = a.copy() // 2
        if cfg.get("water"):
            m = water_mask(a, cfg["water"])
            show[m] = [40, 120, 255]
        if cfg.get("flowers"):
            b = bloom_mask(a)
            show[b] = [255, 60, 200]
        im = Image.fromarray(show.astype(np.uint8))
        sheet.paste(im, ((i % cols) * W + (W - im.width) // 2, (i // cols) * H + (H - im.height) // 2))
    path = os.path.join(OUT, "masks.png")
    sheet.save(path)
    return path

def preview(places):
    """art/animated/preview.html: every GIF at 1x, for a look in a browser (Preview.app shows GIF frames as pages)."""
    cards = "\n".join(f'<figure><img src="{p["id"]}.gif" width="{p["crop"][2]}"><figcaption>{p["name"]}</figcaption></figure>'
                      for p in places if os.path.exists(os.path.join(OUT, f"{p['id']}.gif")))
    with open(os.path.join(OUT, "preview.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html><meta charset="utf-8"><title>Sinnoh scenes, animated</title>
<style>body{{background:#1d1d1d;color:#ddd;font:14px system-ui;margin:16px}}main{{display:flex;flex-wrap:wrap;gap:16px}}
figure{{margin:0}}img{{image-rendering:pixelated;display:block;background:#000}}figcaption{{padding:4px 0}}</style>
<h1 style="font-size:16px">Sinnoh scenes, animated (art/animated/*.gif, shown at 1x)</h1><main>{cards}</main>""")

def main(argv):
    places = json.load(open(os.path.join(ART, "places.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    if "--masks" in argv:
        print(mask_sheet(places)); return
    only = [x for x in argv if not x.startswith("-")]
    for p in places:
        if only and p["id"] not in only:
            continue
        r = build(p, ANIM.get(p["id"], {}))
        if r is None:
            stale = os.path.join(OUT, f"{p['id']}.gif")
            if os.path.exists(stale):
                os.remove(stale)
            print(f"{p['id']:12} nothing to animate")
        else:
            print(f"{p['id']:12} {r['frames']:2d} frames @{r['ms']}ms  water {r['water']:6d}px  blooms {r['blooms']:5d}px  "
                  f"{r['bytes']/1024:6.0f} KB  bodies(size, period, speed, score, still) {r['bodies']}")
    preview(places)

if __name__ == "__main__":
    main(sys.argv[1:])
