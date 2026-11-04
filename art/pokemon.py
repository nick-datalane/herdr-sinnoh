# Chibi Pokémon drawn in code, five poses each, in the same blob-and-outline style as render.py's monsters.
# Poses (the layout's names): idle, walk, smash = the Pokémon's signature move (what it does while the agent
# works), roar = cheering (done), wave = waving (needs you). No mouths; big eyes and blush instead.
# As a module: frames("pikachu") → {pose: RGBA uint8 array}, feet on the bottom row, 1 px dark outline,
# every pose of one Pokémon the same width so the body doesn't jump between frames.
# Standalone: python3 art/pokemon.py <out.png>  → contact sheet of every Pokémon × pose at 3×
import math, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R

CW, CH = 96, 80
FLOOR = 74            # feet rest on this row
POSES = ("idle", "walk", "smash", "roar", "wave")
INK = R.hexc("#1a1c26")
WHITE = R.hexc("#ffffff")
PINK = R.hexc("#ff9fb2")
SPARK = R.hexc("#ffe66d")

# Pose: head offset, body lean, per-leg offset (left, right), arm modes (left, right), eyes
POSE = {
    "idle":  dict(hdx=0, hdy=0, bdx=0, legs=((0, 0), (0, 0)), arms=("down", "down"), eyes="open"),
    "walk":  dict(hdx=1, hdy=0, bdx=0, legs=((-1, -4), (1, 0)), arms=("back", "fwd"), eyes="open"),
    "smash": dict(hdx=2, hdy=1, bdx=1, legs=((-2, 0), (2, 0)), arms=("out", "out2"), eyes="open"),
    "roar":  dict(hdx=0, hdy=-2, bdx=0, legs=((-1, 0), (1, 0)), arms=("up2", "up"), eyes="happy"),
    "wave":  dict(hdx=2, hdy=0, bdx=0, legs=((0, 0), (0, 0)), arms=("down", "up"), eyes="open"),
}

P = R.pal


def pose_of(pose, **over):
    p = dict(POSE[pose])
    p.update(over)
    return p


def rect(s, x0, y0, x1, y1, c):
    s.rect(int(x0), int(y0), int(x1), int(y1), c)


def ellipse(s, cx, cy, rx, ry, c):
    for yy in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for xx in range(int(cx - rx) - 1, int(cx + rx) + 2):
            dx, dy = (xx + 0.5 - cx) / rx, (yy + 0.5 - cy) / ry
            if dx * dx + dy * dy <= 1:
                s.dot(xx, yy, c)


def line(s, x0, y0, x1, y1, c, w=2):
    n = max(1, int(math.hypot(x1 - x0, y1 - y0)))
    for k in range(n + 1):
        t = k / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for dy in range(w):
            for dx in range(w):
                s.dot(int(x) + dx, int(y) + dy, c)


def curve(s, pts, c, w=2):
    for a, b in zip(pts, pts[1:]):
        line(s, *a, *b, c, w)


# ---------- faces ----------

def eyes(s, p, hx, hy, dx=5.5, dy=0, r=(2.9, 3.6), iris=None):
    ey = hy + dy
    for ex in (hx - dx, hx + dx):
        if p["eyes"] == "happy":
            for k in (-2, -1, 0, 1, 2):
                s.dot(int(ex) + k, int(ey) + abs(k) - 1, INK)
                s.dot(int(ex) + k, int(ey) + abs(k), INK)
        elif iris is None:
            s.eye(ex, ey, *r)
        else:
            ellipse(s, ex, ey, r[0], r[1], INK)
            ellipse(s, ex, ey + 0.3, r[0] - 1, r[1] - 1, iris)
            rect(s, ex - r[0] + 1, ey - r[1] + 1, ex - r[0] + 3, ey - r[1] + 3, WHITE)
            s.dot(int(ex + r[0] - 1), int(ey + r[1] - 2), WHITE)


def blush(s, hx, hy, dx=9, dy=4, c=PINK, r=(2.4, 1.6)):
    ellipse(s, hx - dx, hy + dy, r[0], r[1], c)
    ellipse(s, hx + dx, hy + dy, r[0], r[1], c)


# ---------- effects ----------

def sparkle(s, x, y, c=SPARK, r=2):
    for k in range(-r, r + 1):
        s.dot(int(x) + k, int(y), c)
        s.dot(int(x), int(y) + k, c)


def cheer(s, hx, hy, rx=16):
    sparkle(s, hx - rx - 4, hy - 8)
    sparkle(s, hx + rx + 5, hy - 11)
    sparkle(s, hx + rx - 3, hy - rx - 9, r=1)
    sparkle(s, hx - rx + 2, hy - rx - 7, c=WHITE, r=1)


def bolt(s, x0, y0, x1, y1, c=R.hexc("#ffe94a"), core=WHITE, amp=2.5, step=3.5):
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
    ux, uy = (x1 - x0) / n, (y1 - y0) / n
    L = math.hypot(ux, uy)
    px, py = -uy / L, ux / L
    pts = []
    for k in range(n + 1):
        off = amp * (1 if k % 2 else -1) if 0 < k < n else 0
        pts.append((x0 + ux * k + px * off, y0 + uy * k + py * off))
    curve(s, pts, c)
    for ax, ay in pts[1:-1]:
        s.dot(int(ax), int(ay), core)


def note(s, x, y, c):
    ellipse(s, x, y, 2.2, 1.6, c)
    rect(s, x + 1, y - 8, x + 3, y, c)
    for k in range(4):
        s.dot(int(x) + 3 + k, int(y) - 8 + k, c)
        s.dot(int(x) + 3 + k, int(y) - 7 + k, c)


def droplet(s, x, y, rx, ry, c=R.hexc("#86c5ff")):
    ellipse(s, x, y, rx, ry, c)
    s.dot(int(x - rx / 2), int(y - ry / 2), WHITE)


def fireball(s, x, y, r):
    ellipse(s, x, y, r, r * 0.85, R.hexc("#e5432a"))
    ellipse(s, x, y, r * 0.65, r * 0.55, R.hexc("#ff9a2a"))
    ellipse(s, x - r * 0.2, y - r * 0.15, r * 0.3, r * 0.28, R.hexc("#ffe25a"))


# ---------- bodies ----------

# Stub arms for round bodies: rx is the body's half width. "up"/"up2" stack a forearm and a hand above the shoulder.
def arms(s, p, bx, by, rx, pal, r, dy=3, behind=False):
    pos = {
        "down": lambda side: (bx + side * (rx - 1), by + dy),
        "back": lambda side: (bx - rx + 1, by + dy + 1),
        "fwd": lambda side: (bx + rx + 1, by + dy - 4),
        "punch": lambda side: (bx + rx + 3, by - 3),
        "punch2": lambda side: (bx + rx + 1, by + 5),
        "out": lambda side: (bx - rx - 2, by - 5),
        "out2": lambda side: (bx + rx + 2, by - 5),
        "up": lambda side: (bx + rx + 1, by - 3),
        "up2": lambda side: (bx - rx - 1, by - 3),
    }
    for mode, side in zip(p["arms"], (-1, 1)):
        if (mode == "back") != behind:
            continue
        x, y = pos[mode](side)
        s.blob(x, y, r, r, pal)
        if mode in ("up", "up2"):
            d = 1 if mode == "up" else -1
            s.blob(x + 2 * d, y - r - 2, r - 0.6, r + 1, pal)
            s.blob(x + 3 * d, y - 2 * r - 5, r, r, pal)


# Two-legged chibi: big head over a small body, feet at FLOOR. Legs stay planted while the body leans.
class Chibi:
    def __init__(self, s, p, cx=46, head_r=(16, 15), body_r=(12, 10), leg_r=(5, 3.5), arm_r=4.2, neck=5):
        self.s, self.p = s, p
        self.hr, self.br, self.lr, self.ar = head_r, body_r, leg_r, arm_r
        self.cx = cx
        self.bx = cx + p["bdx"]
        self.by = FLOOR - leg_r[1] - body_r[1]
        self.hx = self.bx + p["hdx"]
        self.hy = self.by - body_r[1] - head_r[1] + neck + p["hdy"]

    def legs(self, pal, spread=6):
        for (dx, dy), side in zip(self.p["legs"], (-1, 1)):
            self.s.blob(self.cx + side * spread + dx, FLOOR - self.lr[1] + dy, *self.lr, pal)

    def body(self, pal):
        self.s.blob(self.bx, self.by, *self.br, pal)

    def belly(self, pal, k=0.62, dy=2):
        self.s.blob(self.bx, self.by + dy, self.br[0] * k, self.br[1] * k, pal)

    def head(self, pal):
        self.s.blob(self.hx, self.hy, *self.hr, pal)

    def arms(self, pal, behind=False):
        arms(self.s, self.p, self.bx, self.by, self.br[0], pal, self.ar, dy=2, behind=behind)


# ---------- the eight ----------

def pikachu(s, pose):
    move = pose == "smash"
    p = pose_of(pose)
    c = Chibi(s, p, head_r=(16, 14), body_r=(11, 9))
    yel, tip, brown = P("#f8d030"), P("#2b2620"), P("#8a5a2a")
    bx, by, hx, hy = c.bx, c.by, c.hx, c.hy
    # lightning tail behind the left shoulder
    tx, ty = bx - 11, by - 3
    rect(s, tx + 3, ty + 1, tx + 8, ty + 6, brown[2])
    rect(s, tx - 1, ty - 5, tx + 6, ty + 2, yel[2])
    rect(s, tx - 5, ty - 11, tx + 3, ty - 4, yel[2])
    rect(s, tx - 10, ty - 19, tx + 1, ty - 10, yel[2])
    rect(s, tx - 9, ty - 18, tx - 7, ty - 11, yel[1])
    c.arms(yel, behind=True)
    c.body(yel)
    c.legs(yel)
    c.arms(yel)
    # ears: shrinking blobs climbing away from the head, black tips
    for side in (-1, 1):
        for k in range(4):
            s.blob(hx + side * (9 + 2.4 * k), hy - 11 - 4.3 * k, 3.8 - 0.4 * k, 4.4, tip if k == 3 else yel)
    c.head(yel)
    eyes(s, p, hx, hy)
    if move:    # Thunderbolt: the cheeks glow and bolts fly out of them
        for side in (-1, 1):
            ellipse(s, hx + side * 10, hy + 4, 4.4, 3.8, R.hexc("#fff6b0"))
    blush(s, hx, hy, dx=10, dy=4, c=R.hexc("#e5433a"), r=(2.6, 2.3))
    s.dot(int(hx), int(hy + 4), INK)
    if move:
        bolt(s, hx - 14, hy + 3, hx - 28, hy - 11)
        bolt(s, hx + 14, hy + 3, hx + 28, hy - 11)
        bolt(s, hx + 12, hy - 8, hx + 22, hy - 25)
        for x, y in ((hx - 24, hy + 2), (hx + 30, hy - 2), (hx - 18, hy - 16)):
            s.dot(int(x), int(y), SPARK)
    if pose == "roar":
        cheer(s, hx, hy)


def charmander(s, pose):
    move = pose == "smash"
    p = pose_of(pose, arms=("down", "fwd")) if move else pose_of(pose)
    c = Chibi(s, p, head_r=(16, 14), body_r=(11, 10))
    org, cream = P("#f4913a"), P("#f8dc9a")
    bx, by, hx, hy = c.bx, c.by, c.hx, c.hy
    # tail curling out behind the right side, flame on the tip (bigger while it attacks)
    k = 1.4 if move else 1.0
    s.blob(bx + 12, by + 5, 7, 4, org)
    s.blob(bx + 18, by + 1, 4, 4.5, org)
    s.blob(bx + 19, by - 6 * k, 4.5 * k, 5 * k, P("#e5432a"))
    s.blob(bx + 19, by - 8 * k, 3.2 * k, 3.6 * k, P("#ff9a2a"))
    s.blob(bx + 19, by - 10 * k, 1.8 * k, 2.2 * k, P("#ffe25a"))
    c.arms(org, behind=True)
    c.body(org)
    c.belly(cream, 0.65, 2)
    c.legs(org)
    c.arms(org)
    c.head(org)
    eyes(s, p, hx, hy)
    blush(s, hx, hy)
    if move:    # Ember: a stream of fireballs
        fireball(s, hx + 18, hy + 4, 3.6)
        fireball(s, hx + 25, hy + 1, 3)
        fireball(s, hx + 31, hy - 4, 2.4)
        s.dot(int(hx + 29), int(hy + 5), R.hexc("#ffe25a"))
        s.dot(int(hx + 35), int(hy - 1), R.hexc("#ff9a2a"))
    if pose == "roar":
        cheer(s, hx, hy)


def squirtle(s, pose):
    move = pose == "smash"
    p = pose_of(pose, arms=("down", "fwd")) if move else pose_of(pose)
    c = Chibi(s, p, head_r=(16, 14), body_r=(11, 10))
    blu, shell, rim, plast = P("#74b0e8"), P("#b87a3c"), P("#f0e2a8"), P("#f3e6b4")
    bx, by, hx, hy = c.bx, c.by, c.hx, c.hy
    # curly tail on the left
    s.blob(bx - 14, by + 4, 5, 4, blu)
    s.blob(bx - 18, by, 3.6, 3.6, blu)
    s.blob(bx - 17, by - 4, 2.2, 2.2, blu)
    # shell dome peeking out behind, cream rim
    s.blob(bx - 1, by - 2, 14.5, 11.5, rim)
    s.blob(bx - 1, by - 2, 13, 10, shell)
    c.arms(blu, behind=True)
    c.body(blu)
    c.belly(plast, 0.65, 2)
    c.legs(blu)
    c.arms(blu)
    c.head(blu)
    eyes(s, p, hx, hy, r=(3, 3.7))
    blush(s, hx, hy)
    if move:    # Water Gun: an arc of droplets and some spray
        droplet(s, hx + 17, hy + 4, 3.4, 2.5)
        droplet(s, hx + 23, hy + 2, 3, 2.2)
        droplet(s, hx + 28.5, hy - 1, 2.6, 2)
        droplet(s, hx + 33, hy - 5, 2.2, 1.8)
        for x, y in ((hx + 26, hy - 5), (hx + 31, hy + 3), (hx + 36, hy - 9), (hx + 21, hy - 2)):
            s.dot(int(x), int(y), R.hexc("#d2e9ff"))
    if pose == "roar":
        cheer(s, hx, hy)


def bulbasaur(s, pose):
    move = pose == "smash"
    p = pose_of(pose)
    bx, by = 46 + p["bdx"], FLOOR - 3 - 8
    hx, hy = bx + 7 + p["hdx"], by - 9 + p["hdy"]
    grn, spot, bulb, leaf = P("#7fcfa8"), R.hexc("#3f8f6e"), P("#56b05c"), P("#3f8a44")
    # bulb on the back, behind everything
    s.blob(bx - 9, by - 13, 11, 9.5, bulb)
    s.blob(bx - 14, by - 20, 4, 3, leaf)
    s.blob(bx - 5, by - 22, 4, 3, leaf)
    # back legs
    s.blob(bx - 12, FLOOR - 3.5, 5, 3.5, grn)
    s.blob(bx - 3, FLOOR - 3, 5, 3.5, grn)
    s.blob(bx, by, 15, 9, grn)
    ellipse(s, bx - 10, by + 2, 2.4, 1.8, spot)
    # front legs: walk lifts the left one, waving and cheering raise the right one
    (ldx, ldy), (rdx, rdy) = p["legs"]
    s.blob(bx + 4 + ldx, FLOOR - 3.5 + ldy, 5, 3.5, grn)
    if p["arms"][1] == "up":
        s.blob(bx + 19, by - 3, 4.5, 5, grn)
        s.blob(bx + 21, by - 11, 4, 4, grn)
    else:
        s.blob(bx + 13 + rdx, FLOOR - 3.5, 5, 3.5, grn)
    s.blob(hx, hy, 14, 12, grn)
    ellipse(s, hx - 8, hy - 8, 2.2, 1.8, spot)
    ellipse(s, hx + 7, hy - 9, 1.8, 1.5, spot)
    eyes(s, p, hx, hy, dx=5, r=(2.8, 3.4))
    blush(s, hx, hy, dx=9, dy=4)
    if move:    # Vine Whip: two vines whip out of the bulb
        vine, tipc = R.hexc("#3f9a4a"), R.hexc("#7fd07a")
        curve(s, [(bx - 8, by - 21), (bx, by - 30), (bx + 10, by - 33), (bx + 20, by - 30), (bx + 28, by - 22), (bx + 32, by - 12)], vine)
        ellipse(s, bx + 33, by - 10, 2.6, 1.8, tipc)
        curve(s, [(bx - 12, by - 20), (bx - 20, by - 27), (bx - 24, by - 36), (bx - 20, by - 43)], vine)
        ellipse(s, bx - 19, by - 44, 2.4, 1.6, tipc)
    if pose == "roar":
        cheer(s, hx, hy, rx=14)


def eevee(s, pose):
    move = pose == "smash"
    p = pose_of(pose, bdx=4, hdx=5, hdy=2) if move else pose_of(pose)
    bx, by = 46 + p["bdx"], FLOOR - 3 - 8
    hx, hy = bx + 6 + p["hdx"], by - 11 + p["hdy"]
    brn, cream, dark = P("#c48a4a"), P("#f3e2bf"), R.hexc("#5a3a22")
    if move:    # Quick Attack: speed streaks trail behind
        streak = R.hexc("#fff4dc")
        line(s, bx - 34, by - 7, bx - 22, by - 7, streak)
        line(s, bx - 38, by - 1, bx - 23, by - 1, streak)
        line(s, bx - 33, by + 5, bx - 22, by + 5, streak)
        line(s, bx - 30, hy - 6, bx - 18, hy - 6, streak)
    # bushy tail at the back left
    s.blob(bx - 19, by - 5, 8, 7, brn)
    s.blob(bx - 23, by - 10, 5, 5, cream)
    s.blob(bx - 12, FLOOR - 3.5, 5, 3.5, brn)
    s.blob(bx - 3, FLOOR - 3, 5, 3.5, brn)
    s.blob(bx, by, 15, 9, brn)
    (ldx, ldy), (rdx, rdy) = p["legs"]
    s.blob(bx + 4 + ldx, FLOOR - 3.5 + ldy, 5, 3.5, brn)
    if p["arms"][1] == "up":
        s.blob(bx + 19, by - 3, 4.5, 5, brn)
        s.blob(bx + 21, by - 11, 4, 4, brn)
    else:
        s.blob(bx + 13 + rdx, FLOOR - 3.5, 5, 3.5, brn)
    # fluffy mane between body and head
    s.blob(hx - 3, hy + 9, 12, 6.5, cream)
    # big ears with dark insides
    for side in (-1, 1):
        s.blob(hx + side * 9, hy - 16, 4.5, 8, brn)
        ellipse(s, hx + side * 9, hy - 18, 2, 4.2, dark)
    s.blob(hx, hy, 15, 13, brn)
    eyes(s, p, hx, hy, r=(3, 3.7))
    s.dot(int(hx), int(hy + 4), INK)
    blush(s, hx, hy, dx=10, dy=4)
    if pose == "roar":
        cheer(s, hx, hy, rx=15)


def jigglypuff(s, pose):
    move = pose == "smash"
    p = pose_of(pose, eyes="happy") if move else pose_of(pose)
    bx, by = 46 + p["bdx"], FLOOR - 3 - 16
    hx, hy = bx + p["hdx"] // 2, by + p["hdy"] // 2
    pink, dark = P("#f6b6d2"), R.hexc("#e78ab6")
    # ears and the curl, behind the ball
    for side in (-1, 1):
        s.blob(bx + side * 14, by - 13, 4.5, 5.5, pink)
        ellipse(s, bx + side * 14, by - 14, 1.8, 2.6, dark)
    s.blob(bx - 3, by - 20, 3.5, 3.5, pink)
    s.blob(bx + 2, by - 22, 3, 3, pink)
    s.blob(bx + 6, by - 19, 2.4, 2.4, pink)
    (ldx, ldy), (rdx, rdy) = p["legs"]
    s.blob(bx - 7 + ldx, FLOOR - 3 + ldy, 5.5, 3, pink)
    s.blob(bx + 7 + rdx, FLOOR - 3, 5.5, 3, pink)
    arms(s, p, bx, by, 18, pink, 3.5, dy=5, behind=True)
    s.blob(bx, by, 19, 17, pink)
    arms(s, p, bx, by, 18, pink, 3.5, dy=5)
    eyes(s, p, hx, hy, dx=6.5, dy=-1, r=(4.2, 5), iris=R.hexc("#3f9c88"))
    blush(s, hx, hy, dx=13, dy=5, c=R.hexc("#f08aa8"), r=(2.6, 1.8))
    if move:    # Sing: eyes closed, notes drifting up
        nc = R.hexc("#8a5fd0")
        note(s, bx - 24, by - 12, nc)
        note(s, bx + 24, by - 18, nc)
        note(s, bx + 27, by - 2, nc)
        note(s, bx - 20, by - 28, nc)
    if pose == "roar":
        cheer(s, hx, hy, rx=19)


def gengar(s, pose):
    move = pose == "smash"
    p = pose_of(pose, arms=("punch", "punch2")) if move else pose_of(pose)
    bx, by = 46 + p["bdx"], FLOOR - 3 - 14
    fx, fy = bx + p["hdx"], by - 2 + p["hdy"]
    pur, red = P("#6b4c9e"), R.hexc("#e8322e")
    # ears, top spikes and back spikes, all behind the body
    for side in (-1, 1):
        s.blob(bx + side * 13, by - 13, 4, 6.5, pur)
    for dx, dy in ((-9, -15), (-3, -17), (4, -17), (10, -15)):
        s.blob(bx + dx, by + dy, 2.6, 3.5, pur)
    for dx, dy in ((-18, -4), (-19, 4), (-17, 10)):
        s.blob(bx + dx, by + dy, 3, 2.6, pur)
    (ldx, ldy), (rdx, rdy) = p["legs"]
    s.blob(bx - 7 + ldx, FLOOR - 3 + ldy, 5, 3.2, pur)
    s.blob(bx + 7 + rdx, FLOOR - 3, 5, 3.2, pur)
    arms(s, p, bx, by, 16, pur, 4, dy=4, behind=True)
    s.blob(bx, by, 17, 15, pur)
    arms(s, p, bx, by, 16, pur, 4, dy=4)
    # red eyes with a glint; happy arcs when cheering
    if p["eyes"] == "happy":
        eyes(s, p, fx, fy, dx=6, dy=-3)
    else:
        for side in (-1, 1):
            ellipse(s, fx + side * 6, fy - 3, 4, 3.4, INK)
            ellipse(s, fx + side * 6, fy - 3, 3, 2.5, red)
            rect(s, fx + side * 6 - 2, fy - 5, fx + side * 6, fy - 3, WHITE)
    blush(s, fx, fy, dx=11, dy=2, c=R.hexc("#c98ad6"))
    if move:    # Shadow Ball: a glowing ball of shadow held out in front
        gx, gy = bx + 25, by + 1
        ellipse(s, gx, gy, 7, 6.4, R.hexc("#9b6fe0"))
        ellipse(s, gx, gy, 5.2, 4.7, R.hexc("#4a2a7a"))
        ellipse(s, gx - 1.5, gy - 1.5, 1.6, 1.3, R.hexc("#c9a6ff"))
        for x, y in ((gx - 9, gy - 6), (gx + 8, gy - 8), (gx + 10, gy + 4), (gx - 6, gy + 8), (gx + 2, gy - 10)):
            s.dot(int(x), int(y), R.hexc("#c9a6ff"))
    if pose == "roar":
        cheer(s, fx, fy + 2, rx=17)


def snorlax(s, pose):
    move = pose == "smash"
    p = pose_of(pose, arms=("out", "out2")) if move else pose_of(pose)
    lift = 9 if move else 0
    bx, by = 46 + p["bdx"], FLOOR - 3 - 16 - lift
    hx, hy = bx + p["hdx"], by - 21 + p["hdy"]
    teal, cream = P("#3f7262"), P("#f2e4c0")
    if move:    # Body Slam: airborne, dust and impact marks below
        dust = R.hexc("#cfc8bc")
        for x, r in ((bx - 16, 5), (bx - 6, 6), (bx + 6, 6), (bx + 16, 5)):
            ellipse(s, x, FLOOR - 2, r, 2.2, dust)
        line(s, bx - 26, FLOOR - 9, bx - 22, FLOOR - 5, R.hexc("#f3e2bf"))
        line(s, bx + 24, FLOOR - 9, bx + 20, FLOOR - 5, R.hexc("#f3e2bf"))
    for side in (-1, 1):
        s.blob(hx + side * 10, hy - 8, 3, 4, teal)
    for (dx, dy), side in zip(p["legs"], (-1, 1)):
        x, y = (bx + side * 10 + dx, by + 15) if move else (bx + side * 10 + dx, FLOOR - 3.5 + dy)
        s.blob(x, y, 6, 3.8, teal)
        s.blob(x, y + 0.5, 4, 2.4, cream)
    arms(s, p, bx, by, 19, teal, 5.5, dy=2, behind=True)
    s.blob(bx, by, 20, 16, teal)
    s.blob(bx + 1, by + 3, 13, 11, cream)
    arms(s, p, bx, by, 19, teal, 5.5, dy=2)
    s.blob(hx, hy, 13, 9.5, teal)
    s.blob(hx + 1, hy + 2, 9.5, 5.5, cream)
    # always asleep: closed eyes, happy arcs when cheering
    if p["eyes"] == "happy":
        eyes(s, p, hx, hy, dx=5, dy=1)
    else:
        rect(s, hx - 7, hy, hx - 3, hy + 1, INK)
        rect(s, hx + 3, hy, hx + 7, hy + 1, INK)
    blush(s, hx, hy, dx=9, dy=3, r=(2.2, 1.4))
    if pose == "roar":
        cheer(s, hx, hy, rx=14)


GEN = {
    "pikachu": pikachu, "charmander": charmander, "squirtle": squirtle, "bulbasaur": bulbasaur,
    "jigglypuff": jigglypuff, "eevee": eevee, "gengar": gengar, "snorlax": snorlax,
}


def frames(name):
    R.NIGHT = False    # draw the day palette; build_assets makes the night version
    fn = GEN[name]
    arrs = {}
    for pose in POSES:
        s = R.Sprite(CW, CH)
        fn(s, pose)
        s.outline()
        arrs[pose] = np.clip(s.c, 0, 255).astype(np.uint8)
    xs = [np.where(a[:, :, 3] > 0)[1] for a in arrs.values()]
    x0, x1 = min(int(x.min()) for x in xs), max(int(x.max()) for x in xs) + 1
    out = {}
    for k, a in arrs.items():
        ys = np.where(a[:, :, 3] > 0)[0]
        out[k] = np.ascontiguousarray(a[int(ys.min()):int(ys.max()) + 1, x0:x1])
    return out


def main(out):
    names = list(GEN)
    cell_w, cell_h, k = 84, 76, 3
    img = Image.new("RGBA", (cell_w * len(POSES) * k, cell_h * len(names) * k), (245, 245, 244, 255))
    for i, n in enumerate(names):
        fr = frames(n)
        for j, pose in enumerate(POSES):
            a = fr[pose]
            tile = Image.fromarray(a).resize((a.shape[1] * k, a.shape[0] * k), Image.NEAREST)
            x = (j * cell_w + (cell_w - a.shape[1]) // 2) * k
            y = (i * cell_h + cell_h - 4 - a.shape[0]) * k
            img.alpha_composite(tile, (x, y))
        print(n, {p: fr[p].shape[1::-1] for p in POSES})
    img.save(out)


if __name__ == "__main__":
    main(sys.argv[1])
