# Builds mods/pokemon/assets/: the Sinnoh scenes (art/places.json + art/maps-gen4/), every Pokémon's frames and
# face crops (art/gen4.py), the effect icons, and manifest.json / manifest.js.
# Usage: python3 art/build_assets.py
# Everything is drawn at 1 art pixel = 1 logical pixel and exported 2× with nearest-neighbour scaling
# (on Retina 1 art pixel = 2 device pixels), except where a comment says otherwise.
import json, os, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

ART = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ART)
sys.path.insert(0, ART)
import render as R          # hexc() and puff() for the effect icons

OUT = os.path.join(ROOT, "mods", "pokemon", "assets")
SAMPLES = os.path.join(ART, "samples")
MODES = ("day", "night")
FRAMES = ("idle", "walk", "smash", "roar", "wave")
SPRITE_H = 60
CANVAS_W, CANVAS_H = 400, 480

def save2x(arr_or_img, path, k=2):
    im = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img, "RGBA")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.resize((im.width * k, im.height * k), Image.NEAREST).save(path)

def save1x(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)

def bbox(arr):
    ys, xs = np.where(arr[:, :, 3] > 0)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1

# ---------- Sinnoh scenes ----------
# art/places.json: [{id, name, color, map, crop: [x, y, w, h], stands: [[x, y], ...]}]
#   map: a DS overworld map in art/maps-gen4/ (from the Pokémon Fandom wiki, 1 map px = 1 art px)
#   crop: the window shown in the sidebar (at most 400×480; smaller maps are centred by the mod)
#   stands: where the agents' Pokémon put their feet, in crop coordinates, used in order
def scene_night(img):
    # moonlight: darker and bluer, with a little lift so snow and water still read
    a = np.asarray(img.convert("RGBA")).astype(float)
    a[..., 0] = a[..., 0] * 0.40 + 4
    a[..., 1] = a[..., 1] * 0.46 + 8
    a[..., 2] = a[..., 2] * 0.70 + 24
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")

def thumb(img, size=64):
    # square chip of the scene's middle, smooth-scaled: shown at 20–30 logical px in the top bar and the rail
    s = min(img.width, img.height)
    x0, y0 = (img.width - s) // 2, (img.height - s) // 2
    return img.crop((x0, y0, x0 + s, y0 + s)).resize((size, size), Image.LANCZOS)

def build_places(manifest):
    places = json.load(open(os.path.join(ART, "places.json"), encoding="utf-8"))
    scenes = {}
    for p in places:
        x, y, w, h = p["crop"]
        assert w <= CANVAS_W and h <= CANVAS_H, f"{p['id']}: crop {w}×{h} larger than the canvas"
        full = Image.open(os.path.join(ART, "maps-gen4", p["map"])).convert("RGBA")
        assert x + w <= full.width and y + h <= full.height, f"{p['id']}: crop outside the map"
        day = full.crop((x, y, x + w, y + h))
        for mode, img in (("day", day), ("night", scene_night(day))):
            save2x(img, f"{OUT}/{mode}/places/{p['id']}.png")
            save1x(thumb(img), f"{OUT}/{mode}/places/{p['id']}-thumb.png")
        scenes[p["id"]] = day
        manifest["places"].append({
            "id": p["id"], "name": p["name"], "color": p["color"], "w": w, "h": h,
            "image": f"places/{p['id']}.png", "thumb": f"places/{p['id']}-thumb.png",
            "stands": [{"x": sx, "y": sy} for sx, sy in p["stands"]],
        })
    return scenes

# ---------- Pokémon ----------
def to_night(arr):
    # Night: every pixel darkened to 78 %, except the sparkles of the done pose, which keep glowing
    import gen4 as G
    out = arr.astype(float)
    keep = (arr == G.SPARK).all(-1) | (arr == G.SPARK_CORE).all(-1) | (arr[:, :, 3] == 0)
    out[~keep, :3] *= 0.78
    return np.clip(out, 0, 255).astype(np.uint8)

def pixelize(sheet):
    tmp = tempfile.mkdtemp(prefix="pokemon-px-")
    subprocess.run([sys.executable, "-I", os.path.join(ART, "pixelize.py"), os.path.join(ROOT, sheet), tmp, str(SPRITE_H), "--poses", str(len(FRAMES))],
                   check=True, capture_output=True)
    n = len([f for f in os.listdir(tmp) if f.startswith("frame")])
    assert n == len(FRAMES), f"{sheet}: 切出 {n} 个姿势，应为 {len(FRAMES)}"
    frames = [np.asarray(Image.open(f"{tmp}/frame{k}.png").convert("RGBA")) for k in range(len(FRAMES))]
    shutil.rmtree(tmp)
    return dict(zip(FRAMES, frames))

def in_box(arr, bw, bh):
    # uniform canvas: the feet's midpoint at the bottom centre
    box = np.zeros((bh, bw, 4), dtype=np.uint8)
    fh, fw = arr.shape[:2]
    left = (bw - fw) // 2
    box[bh - fh:, left:left + fw] = arr
    return box

def build_monsters(manifest):
    # The roster (art/roster.json) lists the Pokémon agents can get. Each entry is one of:
    #   {"id", "name", "dex": 25}            a Sinnoh-era game sprite, art/gen4.py (the normal case: all 493)
    #   {"id", "name", "gen": "pikachu"}     a chibi drawn in code by art/pokemon.py
    #   {"id", "name", "sheet": "art/..."}   an AI sprite sheet to pixelize
    # Every Pokémon's files live in monsters/<id>/; poses that look the same share one file, and the
    # manifest only says which file each pose uses ("files"), so 493 entries stay small.
    roster = json.load(open(os.path.join(ART, "roster.json")))
    import gen4 as G
    # signature moves by Dex number (art/sprites-gen4/moves.json): the news card says "<name> used <move>!"
    moves = json.load(open(os.path.join(ART, "sprites-gen4", "moves.json"), encoding="utf-8"))

    def source(m):
        if m.get("dex"):
            return G.frames(m["dex"])
        if m.get("gen"):
            import pokemon as PK
            return PK.frames(m["gen"])
        return pixelize(m["sheet"])

    raw = {m["id"]: source(m) for m in roster}
    bw = max(f.shape[1] for fr in raw.values() for f in fr.values()) + 4
    bh = max(f.shape[0] for fr in raw.values() for f in fr.values())
    bw += bw % 2; bh += bh % 2
    manifest["sprite"] = {"w": bw, "h": bh, "ax": bw // 2, "ay": bh}
    # which file each pose uses (only the done pose differs); the face crops are the same for every pose
    POSE_FILE = {"idle": "idle.png", "walk": "idle.png", "smash": "idle.png", "roar": "roar.png", "wave": "idle.png"}
    manifest["files"] = {"frames": POSE_FILE, "head": "head.png", "avatar": "avatar.png", "face": "face.png"}
    sprites = {}
    for m in roster:
        mid, fr = m["id"], raw[m["id"]]
        for mode in MODES:
            conv = (lambda a: a) if mode == "day" else to_night
            for k in sorted(set(POSE_FILE.values())):
                pose = next(p for p, f in POSE_FILE.items() if f == k)
                save2x(in_box(conv(fr[pose]), bw, bh), f"{OUT}/{mode}/monsters/{mid}/{k}")
            # face crops of the idle pose: 48×48 shown at 24 (pane header, tabs) and at 48 (roster, 2×);
            # 32×32 shown at 32 (news card, 2×)
            f48 = conv(G.face(fr["idle"], 48))
            f32 = conv(G.face(fr["idle"], 32))
            save1x(Image.fromarray(f48, "RGBA"), f"{OUT}/{mode}/monsters/{mid}/head.png")
            save2x(f48, f"{OUT}/{mode}/monsters/{mid}/avatar.png")
            save2x(f32, f"{OUT}/{mode}/monsters/{mid}/face.png")
        sprites[mid] = {k: in_box(fr[k], bw, bh) for k in FRAMES}
        entry = {"id": mid, "name": m["name"], "top": bh - fr["idle"].shape[0]}
        if m.get("dex"):
            entry["dex"] = m["dex"]
            entry["move"] = moves.get(str(m["dex"]), "Tackle")
        manifest["monsters"].append(entry)
    return sprites

# ---------- effect icons (character art) ----------
FX = {
    "bang": ("""
.KKKKKKKKKKK.
KWWWWWWWWWWWK
KWWWRRWRRWWWK
KWWWRRWRRWWWK
KWWWRRWRRWWWK
KWWWRRWRRWWWK
KWWWWWWWWWWWK
KWWWRRWRRWWWK
KWWWWWWWWWWWK
.KKKKWWKKKKK.
....KWK......
....KK.......""", {"K": "#2b2620", "W": "#ffffff", "R": "#e8402f"}),
    "question": ("""
.KKKKKKKKKKK.
KWWWWWWWWWWWK
KWWWWBBBWWWWK
KWWWBWWWBWWWK
KWWWWWWWBWWWK
KWWWWWWBWWWWK
KWWWWWBWWWWWK
KWWWWWWWWWWWK
KWWWWWBWWWWWK
KWWWWWWWWWWWK
.KKKKWWKKKKK.
....KWK......
....KK.......""", {"K": "#2b2620", "W": "#ffffff", "B": "#2f6fe0"}),
    # sleeping: a big Z and a small z that drift up over a resting Pokémon
    "z1": ("""
KKKKKKK
KZZZZZK
KKKKZZK
..KZZK.
.KZZK..
KZZZZZK
KKKKKKK""", {"K": "#2b3a55", "Z": "#9cc7ff"}),
    "z2": ("""
KKKKK
KzzzK
KKzKK
KzzzK
KKKKK""", {"K": "#2b3a55", "z": "#c9e0ff"}),
    "siren": ("""
.KKK.
KRWRK
KRRRK
KKKKK""", {"K": "#2b2620", "R": "#ff3b3b", "W": "#ffd0d0"}),
    "brick": ("""
KKKKKKKKKKKK
KBBBBKBBBBBK
KBBBBKBBBBBK
KKKKKKKKKKKK
KBBKBBBBBKBK
KBBKBBBBBKBK
KKKKKKKKKKKK
KBBBBBKBBBBK
KBBBBBKBBBBK
KKKKKKKKKKKK""", {"K": "#6b3524", "B": "#d9673f"}),
    # music notes floating over a working Pokémon (scene) and pinned to its card photo (roster)
    "note1": ("""
....KK..
....KFK.
....KFFK
....K.KK
....K...
....K...
....K...
.KKKK...
KFFFK...
KFFFK...
.KKK....""", {"K": "#2b2620", "F": "#ff8fb1"}),
    "note2": ("""
....KKKKKKK
....KFFFFFK
....KKKKKKK
....K.....K
....K.....K
....K.....K
.KKKK..KKKK
KFFFK.KFFFK
KFFFK.KFFFK
.KKK...KKK.""", {"K": "#2b2620", "F": "#86c5ff"}),
    "note3": ("""
....KK..
....KFK.
....KFFK
....K.KK
....K...
....K...
....K...
.KKKK...
KFFFK...
KFFFK...
.KKK....""", {"K": "#2b2620", "F": "#ffd23f"}),
    # the paper clip on the card photo
    "clip": ("""
.KKKK.
KSSSSK
KS..SK
KS.KSK
KS.KSK
KS.KSK
KS.KSK
KSSKSK
.KKKSK
...KSK
...KSK
....K.""", {"K": "#5a5f6b", "S": "#d5d8de"}),
}

def fx_bitmap(art, colors, mode):
    rows = [r for r in art.strip("\n").split("\n")]
    w = max(len(r) for r in rows)
    out = np.zeros((len(rows), w + (w % 2), 4), dtype=np.uint8)
    for yy, r in enumerate(rows):
        for xx, ch in enumerate(r):
            if ch in colors:
                c = R.hexc(colors[ch]).astype(int)
                if mode == "night" and ch in "KB" and colors is FX["brick"][1]:
                    c[:3] = (c[:3] * 0.8).astype(int)
                out[yy, xx] = c
    return out

def build_fx(mode, manifest):
    sizes = {}
    for name, (art, colors) in FX.items():
        arr = fx_bitmap(art, colors, mode)
        save2x(arr, f"{OUT}/{mode}/fx/{name}.png")
        sizes[name] = [arr.shape[1], arr.shape[0]]
    if mode == "day":
        manifest["fx"] = {k: f"fx/{k}.png" for k in sizes}
        manifest["fxSize"] = sizes      # logical [w, h]

# ---------- checks ----------
def verify(manifest):
    names = []
    for p in manifest["places"]:
        names += [p["image"], p["thumb"]]
    files = manifest["files"]
    for m in manifest["monsters"]:
        names += [f"monsters/{m['id']}/{f}" for f in set(files["frames"].values()) | {files["head"], files["avatar"], files["face"]}]
    names += list(manifest["fx"].values())
    sizes = {p["image"]: (p["w"] * 2, p["h"] * 2) for p in manifest["places"]}
    for mode in MODES:
        for n in names:
            path = f"{OUT}/{mode}/{n}"
            assert os.path.exists(path), f"missing {path}"
            w, h = Image.open(path).size
            assert w % 2 == 0 and h % 2 == 0, f"odd size {path} {w}×{h}"
            if n in sizes:
                assert (w, h) == sizes[n], f"scene size {path} {w}×{h} ≠ {sizes[n]}"
    return len(names) * len(MODES)

def check_image(manifest, scenes, sprites):
    # every scene with a Pokémon on each stand (feet at the stand, drawn back to front), 4 per row, 1×
    ids = [m["id"] for m in manifest["monsters"]]
    picks = [i for i in ("025", "143", "393", "448", "094", "006", "133", "471") if i in sprites] or ids[:4]
    sp = manifest["sprite"]
    cols, cw, ch = 4, CANVAS_W, CANVAS_H
    places = manifest["places"]
    sheet = Image.new("RGBA", (cols * cw, -(-len(places) // cols) * ch), (245, 245, 244, 255))
    for n, p in enumerate(places):
        cell = Image.new("RGBA", (cw, ch), (245, 245, 244, 255))
        ox, oy = (cw - p["w"]) // 2, (ch - p["h"]) // 2
        cell.alpha_composite(scenes[p["id"]], (ox, oy))
        for k, st in enumerate(sorted(p["stands"], key=lambda s: s["y"])):
            img = Image.fromarray(sprites[picks[(n + k) % len(picks)]]["idle"], "RGBA")
            cell.alpha_composite(img, (ox + st["x"] - sp["ax"], oy + st["y"] - sp["ay"]))
        sheet.paste(cell, ((n % cols) * cw, (n // cols) * ch))
    os.makedirs(SAMPLES, exist_ok=True)
    sheet.save(f"{SAMPLES}/assets-check.png")
    # every 7th Pokémon's 48 px face crop at 2×, 12 per row: the roster photos as the cards show them
    ids7 = ids[::7]
    cols, cell = 12, 56
    faces = Image.new("RGBA", (cols * cell, -(-len(ids7) // cols) * cell), (245, 245, 244, 255))
    for n, mid in enumerate(ids7):
        im = Image.open(f"{OUT}/day/monsters/{mid}/avatar.png").convert("RGBA").resize((48, 48), Image.NEAREST)
        faces.alpha_composite(im, ((n % cols) * cell + 4, (n // cols) * cell + 4))
    faces.resize((faces.width * 2, faces.height * 2), Image.NEAREST).save(f"{SAMPLES}/assets-faces.png")

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    manifest = {"canvas": {"w": CANVAS_W, "h": CANVAS_H}, "places": [], "monsters": []}
    scenes = build_places(manifest)
    for mode in MODES:
        build_fx(mode, manifest)
    sprites = build_monsters(manifest)
    with open(f"{OUT}/manifest.json", "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "mods", "pokemon", "manifest.js"), "w") as f:
        f.write("// generated by art/build_assets.py, don't edit\nexport default " + json.dumps(manifest, ensure_ascii=False) + ";\n")
    n = verify(manifest)
    check_image(manifest, scenes, sprites)
    print(f"ok: {n} files, {len(manifest['places'])} places, {len(manifest['monsters'])} Pokémon → {OUT}")

if __name__ == "__main__":
    main()
