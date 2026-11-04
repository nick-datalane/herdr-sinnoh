"""Undo the evening tint baked into a Platinum map rip.

The Fandom wiki's "Floaroma Meadow Pt.png" was captured at dusk, so the game's
blue evening tint is in the pixels. This fits a per-channel gain/offset by
matching palette colours (ICP in RGB space) between a window of the tinted map
and a daytime Diamond/Pearl screenshot of the same tiles, then applies it to
the whole map.

    python3 art/daylight.py art/maps-gen4/raw/floaroma-pt-evening.png \
        art/maps-gen4/raw/floaroma-dp-day-ref.png art/maps-gen4/floaroma.png

Optional 4th/5th args: source and reference windows as x0,y0,x1,y1
(defaults are the house + honey tree in both images).
"""
import sys
import numpy as np
from PIL import Image

src, ref, out = sys.argv[1:4]
sbox = tuple(map(int, sys.argv[4].split(","))) if len(sys.argv) > 4 else (540, 455, 730, 585)
rbox = tuple(map(int, sys.argv[5].split(","))) if len(sys.argv) > 5 else (0, 0, 190, 95)

S = np.asarray(Image.open(src).convert("RGB")).astype(float)
R = np.asarray(Image.open(ref).convert("RGB")).astype(float)


def palette(a, minc):
    v, c = np.unique(a.reshape(-1, 3), axis=0, return_counts=True)
    k = c >= minc
    return v[k], c[k]


Sp, Sc = palette(S[sbox[1]:sbox[3], sbox[0]:sbox[2]], 12)
Rp, Rc = palette(R[rbox[1]:rbox[3], rbox[0]:rbox[2]], 12)
gain = np.array([1.5, 1.5, 1.2])
off = np.zeros(3)
for it in range(12):
    T = Sp * gain + off
    d = np.linalg.norm(T[:, None, :] - Rp[None, :, :], axis=2)
    j = d.argmin(1)
    dist = d[np.arange(len(Sp)), j]
    keep = dist < (40 if it < 3 else 22)
    w = np.sqrt(Sc[keep])
    for c in range(3):
        A = np.c_[Sp[keep, c], np.ones(keep.sum())] * w[:, None]
        (gain[c], off[c]), *_ = np.linalg.lstsq(A, Rp[j[keep], c] * w, rcond=None)
print("matched %d/%d palette colours, median distance %.1f" % (keep.sum(), len(Sp), np.median(dist[keep])))
print("gain", gain.round(3), "offset", off.round(1))
O = np.clip(S * gain + off, 0, 255).round().astype(np.uint8)
Image.fromarray(O).save(out)
print("wrote", out)
