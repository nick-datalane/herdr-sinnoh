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
    # the tall grass rustles one tile at a time, in turn at a few spots, as when something moves through it
    "eterna":      {"rustle": 5},
    "sunyshore":   {"water": (70, 30, 140)},
    "snowpoint":   {"snow": True},
    "valor-beach": {"water": (70, 25, 130)},
    # the waterfall is cut out of the pool above it, so each scrolls with its own texture
    "league":      {"water": (50, 15, 120), "split": [[111, 229, 176, 142]]},
    # the hot-spring pools are teal, not blue: found by their own rule (g - r, |g - b|, g); no flowers (the rule
    # takes the white fence posts for blooms)
    "resort":      {"water": (60, 20, 120), "glint": True, "pools": (35, 20, 150)},
    "paradise":    {"water": (60, 20, 120), "flowers": True},
    "twinleaf":    {"water": (60, 20, 120), "glint": True},
    # the fountain bowls are too small to scroll (it only smears the rim shading): their rings are redrawn, flowing out
    "hearthome":   {"fountains": True},
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

def pool_mask(a, cfg):
    """Teal water (a hot spring): green and blue alike, both well above red."""
    gr, gb, gmin = cfg
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g - r > gr) & (np.abs(g - b) < gb) & (g > gmin)
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=1))
    lab, n = ndimage.label(m)
    out = []
    for i in range(1, n + 1):
        cm = lab == i
        if cm.sum() >= MIN_WATER_PX:
            q = (a[cm] // 8).astype(np.int32)
            _, inv, cnt = np.unique(q, axis=0, return_inverse=True, return_counts=True)
            out.append(dict(mask=cm, size=int(cm.sum()), base=a[cm][inv == int(np.argmax(cnt))].mean(0)))
    return out

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
    out, flat = [], []
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
                    flat.append(dict(mask=cm, size=int(cm.sum()), base=base))
                    continue
            # a pixel moves when the one a period below or above it is the same colour (and in the body)
            down = np.zeros_like(cm); down[:-P] = cm[P:] & near(a[:-P], a[P:])
            up = np.zeros_like(cm); up[P:] = cm[:-P] & near(a[P:], a[:-P])
            still = cm & ~(down | up)
            still = ndimage.binary_opening(still, structure=np.ones((3, 3)))   # not lone noisy pixels
            out.append(dict(mask=cm & ~still, size=int(cm.sum()), period=P, score=score, still=int(still.sum())))
    out.sort(key=lambda b: -b["size"])
    return out, flat

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

def sway(a, mask, ground, dx, land):
    """Lift the mask's pixels off (the ground shows), set them down dx pixels over (a number, or an array per pixel),
    only where they land on `land` or on the mask itself, never on a path or a wall."""
    dx = np.broadcast_to(np.asarray(dx), mask.shape)
    mv = mask & (dx != 0)
    if not mv.any():
        return a
    out = a.copy()
    out[mv] = ground[mv]
    ys, xs = np.nonzero(mv)
    nx = xs + dx[ys, xs]
    ok = (nx >= 0) & (nx < a.shape[1])
    ys, xs, nx = ys[ok], xs[ok], nx[ok]
    ok = mask[ys, nx] | land[ys, nx]
    out[ys[ok], nx[ok]] = a[ys[ok], xs[ok]]
    return out

def sway_flowers(a, blooms, ground, dx):
    return sway(a, blooms, ground, dx, is_grass(a))

# ---- effects drawn on top (snow, glints, fountain rings, grass rustles): each loops over the frame count it is given ----

def rng(p):
    return np.random.default_rng(sum(map(ord, p["id"])))   # the same scene gives the same GIF on every build

SNOW = [  # (size in map px, rows per frame, flakes per 1000 px², colour): far flakes small and slow, near ones big
    (1, 1, 4.0, (228, 234, 248)),
    (2, 2, 1.8, (255, 255, 255)),
    (2, 3, 1.0, (255, 255, 255)),
]
SNOW_EDGE = (150, 165, 195)   # a 2 px flake's lower right edge, so it shows against snow

def snow_layers(r, h, w, n):
    """Each layer is a tile of n*speed rows (one loop moves it exactly one tile down), so the snowfall is seamless;
    the tiles of the three layers differ in height, so the repeat doesn't show."""
    out = []
    for size, v, dens, col in SNOW:
        th = n * v
        cnt = max(1, int(dens * th * w / 1000))
        out.append(dict(size=size, v=v, th=th, col=np.array(col), x=r.integers(0, w, cnt), y=r.integers(0, th, cnt),
                        ph=r.uniform(0, 2 * np.pi, cnt), amp=r.choice([0, 1, 1, 2], cnt) if size > 1 or v > 1 else np.zeros(cnt, int)))
    return out

def draw_snow(f, layers, k, n):
    h, w = f.shape[:2]
    for L in layers:
        y0 = (L["y"] + k * L["v"]) % L["th"]
        x = (L["x"] + np.round(L["amp"] * np.sin(2 * np.pi * k / n + L["ph"])).astype(int)) % w
        for rep in range(0, h + L["th"], L["th"]):
            y = y0 + rep - L["th"]
            if L["size"] > 1:   # the edge first, then the flake over it: an L of shade below and to the right
                for dy, dx in ((2, 1), (2, 2), (1, 2)):
                    yy, xx = y + dy, (x + dx) % w
                    ok = (yy >= 0) & (yy < h)
                    f[yy[ok], xx[ok]] = SNOW_EDGE
            for dy in range(L["size"]):
                for dx in range(L["size"]):
                    yy, xx = y + dy, (x + dx) % w
                    ok = (yy >= 0) & (yy < h)
                    f[yy[ok], xx[ok]] = L["col"]
    return f

GLINT = [  # a glint's life in frames: a dot, a small cross, a dot, gone
    [(0, 0)],
    [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)],
    [(0, 0)],
]
GLINT_PX = 350          # one glint at a time per this many map px of flat water

def glints(r, flat, n):
    out = []
    for b in flat:
        inner = ndimage.binary_erosion(b["mask"], iterations=3)
        ys, xs = np.nonzero(inner)
        if not len(ys):
            continue
        col = np.minimum(255, b["base"] + (255 - b["base"]) * 0.75)
        lives = max(1, b["size"] // GLINT_PX) * n // (len(GLINT) + 2)
        for i in range(lives):
            j = r.integers(len(ys))
            out.append((ys[j], xs[j], int(r.integers(n)), col))
    return out

def draw_glints(f, gl, k, n):
    h, w = f.shape[:2]
    for y, x, ph, col in gl:
        t = (k - ph) % n
        if t < len(GLINT):
            for dy, dx in GLINT[t]:
                if 0 <= y + dy < h and 0 <= x + dx < w:
                    f[y + dy, x + dx] = col
    return f

RING_GAP = 8            # map px between the rings that flow down a fountain's tiers, one px per frame

def fountains(a):
    """Every fountain: the pale cyan water and its white rings, and where the jet tops out."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cyan = (g > 185) & (b > 170) & (g - r > 40)
    white = (a.min(-1) > 205) & (b >= r)
    lab, n = ndimage.label(ndimage.binary_closing(cyan, iterations=1))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        m = ndimage.binary_fill_holes(lab == i)
        if m.sum() < 400:
            continue
        m = ndimage.binary_fill_holes(m | (white & ndimage.binary_dilation(m, iterations=2)))
        ys, xs = np.nonzero(m)
        top = ys.min()
        cx = xs[ys < top + 4].mean()
        rings = m & white
        water = m & ~rings
        out.append(dict(mask=m, rings=rings, water=water, top=top, cx=cx,
                        light=np.median(a[rings], 0) if rings.any() else np.array([228, 246, 246]),
                        fill=ground_fill(a, rings)))
    return out

def draw_fountains(f, a, fts, k):
    for ft in fts:
        m = ft["mask"]
        ys, xs = np.nonzero(m)
        f[ft["rings"]] = ft["fill"][ft["rings"]]
        # the rings bow up at the sides like the tiers do; they flow down from the jet and wrap every RING_GAP
        d = (ys - ft["top"]) - 0.35 * np.abs(xs - ft["cx"]) - k
        ph = np.floor(d) % RING_GAP
        lit = (ph == 0) & (ys > ft["top"] + 3)
        half = (ph == 1) & (ys > ft["top"] + 3)
        f[ys[lit], xs[lit]] = ft["light"]
        f[ys[half], xs[half]] = (f[ys[half], xs[half]] + ft["light"]) // 2
    return f

TILE = 16               # the DS map tile, in map px
RUSTLE = [2, -2]        # a tuft's shake: two pixels over, two back past centre, then still
RUSTLE_MS = 110
RUSTLE_REST_MS = 900    # still between one tile's rustle and the next

def tall_grass(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g - r > 60) & (b < 75) & (g < 215) & (g > 90)

def rustle_tiles(a, r, count):
    """`count` tall grass tiles, spread over the scene. The tile grid is found as the offset with the most tiles that
    are nearly all grass (a misaligned grid cuts every tuft); tiles are picked far from each other (each next one
    the farthest from those picked)."""
    m = tall_grass(a)
    h, w = m.shape
    best = None
    for oy in range(TILE):
        for ox in range(TILE):
            cov = [m[y:y + TILE, x:x + TILE].mean() for y in range(oy, h - TILE + 1, TILE) for x in range(ox, w - TILE + 1, TILE)]
            sc = sum(c for c in cov if c > 0.5)
            if best is None or sc > best[0]:
                best = (sc, ox, oy)
    _, ox, oy = best
    full = [(y, x) for y in range(oy, h - TILE + 1, TILE) for x in range(ox, w - TILE + 1, TILE)
            if m[y:y + TILE, x:x + TILE].mean() > 0.45]
    if not full:
        return [], m
    pick = [full[int(r.integers(len(full)))]]
    while len(pick) < min(count, len(full)):
        d = [min(abs(y - py) + abs(x - px) for py, px in pick) for y, x in full]
        pick.append(full[int(np.argmax(d))])
    # a tuft is shorter than a tile (two rows of them per tile, with a gap): rustle the one tuft at the tile's
    # middle, the rows between the gaps above and below it, so no tuft is ever cut in half
    out = []
    for ty, tx in pick:
        col = m[:, tx:tx + TILE].mean(1)
        y0 = y1 = ty + TILE // 2
        while y0 > 0 and col[y0 - 1] > 0.15:
            y0 -= 1
        while y1 < h - 1 and col[y1 + 1] > 0.15:
            y1 += 1
        out.append((y0, min(y1 + 1, y0 + 2 * TILE), tx, tx + TILE))
    return out, m

def to2x(arr):
    return Image.fromarray(arr.astype(np.uint8)).resize((arr.shape[1] * 2, arr.shape[0] * 2), Image.NEAREST)

def build(p, cfg, out=OUT):
    a = load(p)
    h, w = a.shape[:2]
    r = rng(p)
    wm = water_mask(a, cfg["water"]) if cfg.get("water") else None
    if wm is not None and wm.sum() < MIN_WATER_PX:
        wm = None
    fl = bloom_mask(a) if cfg.get("flowers") else None
    if fl is not None and fl.sum() < 20:
        fl = None
    bod, flat = bodies(a, wm, cfg.get("split", ())) if wm is not None else ([], [])
    if cfg.get("pools"):
        flat = flat + pool_mask(a, cfg["pools"])
    gl_on = cfg.get("glint") and flat
    fts = fountains(a) if cfg.get("fountains") else []
    tiles = []
    if cfg.get("rustle"):
        tiles, grass = rustle_tiles(a, r, cfg["rustle"])
    if not (bod or fl is not None or gl_on or fts or cfg.get("snow") or tiles):
        return None
    if bod:
        n, speeds = loop_length(bod)
    elif tiles:
        n, speeds = len(tiles) * (len(RUSTLE) + 1), []
    else:
        n, speeds = FLOWER_FRAMES, []
    ms = FRAME_MS + 30 if 2 in speeds else FRAME_MS   # bodies at 2 px per frame get a little longer per frame
    durations = [ms] * n
    hold = max(1, n // len(SWAY))
    ground = ground_fill(a, fl) if fl is not None else None
    snow = snow_layers(r, h, w, n) if cfg.get("snow") else None
    gl = glints(r, flat, n) if gl_on else []
    if tiles:
        g_ground = ground_fill(a, grass)
        durations = ([RUSTLE_MS] * len(RUSTLE) + [RUSTLE_REST_MS]) * len(tiles)
    frames = []
    for k in range(n):
        f = a.copy()
        for b, sp in zip(bod, speeds):
            scroll_body(f, a, b["mask"], k * sp, b["period"])
        if fl is not None:
            f = sway_flowers(f, fl, ground, SWAY[(k // hold) % len(SWAY)])
        if gl:
            f = draw_glints(f, gl, k, n)
        if fts:
            f = draw_fountains(f, a, fts, k)
        if tiles and k % (len(RUSTLE) + 1) < len(RUSTLE):
            y0, y1, x0, x1 = tiles[k // (len(RUSTLE) + 1)]
            dx = np.zeros((h, w), int)
            dx[y0:y1, x0:x1] = RUSTLE[k % (len(RUSTLE) + 1)]
            f = sway(f, grass, g_ground, dx, is_grass(a))
        if snow:
            f = draw_snow(f, snow, k, n)
        frames.append(to2x(f))
    # one palette for every frame, built from all of them (snow and glints add colours frame 0 lacks); no dither
    strip = Image.new("RGB", (frames[0].width, frames[0].height * len(frames)))
    for i, fr in enumerate(frames):
        strip.paste(fr, (0, i * fr.height))
    pal = strip.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{p['id']}.gif")
    q[0].save(path, save_all=True, append_images=q[1:], loop=0, duration=durations, disposal=1, optimize=False)
    fx = [k for k in ("snow", "glint", "fountains", "rustle") if cfg.get(k)]
    return dict(path=path, frames=n, ms=ms, water=int(wm.sum()) if wm is not None else 0,
                bodies=[(b["size"], b["period"], sp, round(b["score"], 2), b["still"]) for b, sp in zip(bod[:4], speeds)],
                blooms=int(fl.sum()) if fl is not None else 0, bytes=os.path.getsize(path),
                fx=fx, glints=len(gl), fountains=len(fts))

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
        if cfg.get("pools"):
            for b in pool_mask(a, cfg["pools"]):
                show[b["mask"]] = [0, 230, 160]
        if cfg.get("fountains"):
            for ft in fountains(a):
                show[ft["water"]] = [40, 220, 220]; show[ft["rings"]] = [255, 255, 255]
        if cfg.get("rustle"):
            show[tall_grass(a)] = [255, 200, 0]
            for y0, y1, x0, x1 in rustle_tiles(a, rng(p), cfg["rustle"])[0]:
                show[y0:y1, x0:x1] = [255, 40, 40]
        im = Image.fromarray(show.astype(np.uint8))
        sheet.paste(im, ((i % cols) * W + (W - im.width) // 2, (i // cols) * H + (H - im.height) // 2))
    path = os.path.join(OUT, "masks.png")
    sheet.save(path)
    return path

def preview(places, only=()):
    """art/animated/preview.html: every GIF next to its still scene, both at the size Herdr shows them on a Retina
    screen (Preview.app shows GIF frames as pages, so use a browser). Given place ids, only those."""
    still = os.path.join(ART, "..", "mods", "pokemon", "assets", "day", "places")
    cards = []
    for p in places:
        if (only and p["id"] not in only) or not os.path.exists(os.path.join(OUT, f"{p['id']}.gif")):
            continue
        w = p["crop"][2]
        cards.append(f'<section><h2>{p["name"]}</h2><div><figure><img src="{p["id"]}.gif" width="{w}"><figcaption>animated</figcaption></figure>'
                     f'<figure><img src="{os.path.relpath(still, OUT)}/{p["id"]}.png" width="{w}"><figcaption>still</figcaption></figure></div></section>')
    with open(os.path.join(OUT, "preview.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html><meta charset="utf-8"><title>Sinnoh scenes, animated</title>
<style>body{{background:#1d1d1d;color:#ddd;font:14px system-ui;margin:16px}}main{{display:flex;flex-wrap:wrap;gap:32px}}
section div{{display:flex;gap:8px}}h2{{font-size:14px;margin:0 0 6px}}figure{{margin:0}}
img{{image-rendering:pixelated;display:block;background:#000}}figcaption{{padding:4px 0;color:#999}}</style>
<h1 style="font-size:16px">Sinnoh scenes, animated next to still</h1><main>{"".join(cards)}</main>""")

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
                  f"{r['bytes']/1024:6.0f} KB  bodies(size, period, speed, score, still) {r['bodies']}"
                  + (f"  fx {r['fx']} glints {r['glints']} fountains {r['fountains']}" if r['fx'] else ""))
    preview(places, only)

if __name__ == "__main__":
    main(sys.argv[1:])
