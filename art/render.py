# 等距像素渲染器 v2：逐像素等距投影 + 深度缓冲 + 自动描边/高光 + 分层光照圆球（萌系怪兽）
# 用法：python3 -I art/render.py <输出目录> [day|night]   → 整幅场景（v4 样张）
# 作为模块：reset(mode) → draw_plate() / draw_slot(i, damage) → layer(objs)，供 build_assets.py 拆层导出
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw

NIGHT = False
W, H = 400, 480
OX, OY = 200, 272
SCALE = 3

def hexc(h):
    return np.array([int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255], dtype=float)

def shade(c, k):
    c = np.array(c, dtype=float)
    rgb = c[:3] + (255 - c[:3]) * k if k >= 0 else c[:3] * (1 + k)
    return np.array([*np.clip(rgb, 0, 255), c[3]])

def night(c, k=-0.38):
    return shade(c, k) if NIGHT else c

# ---------- 画布缓冲 ----------
COL = DEP = OBJ = FACE = None           # OBJ：物体编号，0 = 空；FACE：0 无 / 1 顶面 / 2 左前面 / 3 右前面 / 4 精灵
_next = [1]

def reset(mode="day"):
    global NIGHT, COL, DEP, OBJ, FACE
    NIGHT = mode == "night"
    COL = np.zeros((H, W, 4))
    DEP = np.full((H, W), -1e9)
    OBJ = np.zeros((H, W), dtype=int)
    FACE = np.zeros((H, W), dtype=int)
    _next[0] = 1

def snapshot():
    return (COL.copy(), DEP.copy(), OBJ.copy(), FACE.copy(), _next[0])

def restore(snap):
    global COL, DEP, OBJ, FACE
    COL, DEP, OBJ, FACE = (a.copy() for a in snap[:4])
    _next[0] = snap[4]

def new_obj():
    _next[0] += 1
    return _next[0]

def plot(sx, sy, depth, color, obj, face):
    if 0 <= sx < W and 0 <= sy < H and depth >= DEP[sy, sx]:
        DEP[sy, sx] = depth
        COL[sy, sx] = color
        OBJ[sy, sx] = obj
        FACE[sy, sx] = face

def P(x, y, z=0.0):
    return OX + (x - y), OY + (x + y) / 2 - z

# 顶面：z 高度处的矩形 [x0,x1)×[y0,y1)，color(x,y) 返回颜色或 None
def top(x0, y0, x1, y1, z, color, obj, face=1, bias=0.0):
    pts = [P(x0, y0, z), P(x1, y0, z), P(x1, y1, z), P(x0, y1, z)]
    sxs = [p[0] for p in pts]; sys_ = [p[1] for p in pts]
    for sy in range(int(min(sys_)) - 1, int(max(sys_)) + 2):
        for sx in range(int(min(sxs)) - 1, int(max(sxs)) + 2):
            a = sx + 0.5 - OX
            b = 2 * (sy + 0.5 - OY + z)
            x, y = (a + b) / 2, (b - a) / 2
            if x0 <= x < x1 and y0 <= y < y1:
                c = color(x, y)
                if c is not None:
                    plot(sx, sy, x + y + z + bias, c, obj, face)

# 左前面：平面 y = yf，x∈[x0,x1)，z∈[z0,z1)
def left(x0, x1, yf, z0, z1, color, obj):
    for sx in range(int(OX + x0 - yf) - 1, int(OX + x1 - yf) + 2):
        x = sx + 0.5 - OX + yf
        if not (x0 <= x < x1):
            continue
        base = OY + (x + yf) / 2
        for sy in range(int(base - z1) - 1, int(base - z0) + 2):
            z = base - (sy + 0.5)
            if z0 <= z < z1:
                c = color(x - x0, z - z0)
                if c is not None:
                    plot(sx, sy, x + yf + z, c, obj, 2)

# 右前面：平面 x = xf，y∈[y0,y1)
def right(xf, y0, y1, z0, z1, color, obj):
    for sx in range(int(OX + xf - y1) - 1, int(OX + xf - y0) + 2):
        y = OX + xf - (sx + 0.5)
        if not (y0 <= y < y1):
            continue
        base = OY + (xf + y) / 2
        for sy in range(int(base - z1) - 1, int(base - z0) + 2):
            z = base - (sy + 0.5)
            if z0 <= z < z1:
                c = color(y - y0, z - z0)
                if c is not None:
                    plot(sx, sy, xf + y + z, c, obj, 3)

def box(x, y, z, w, d, h, ctop, cleft, cright, obj=None):
    obj = obj or new_obj()
    left(x, x + w, y + d, z, z + h, cleft if callable(cleft) else (lambda u, v: cleft), obj)
    right(x + w, y, y + d, z, z + h, cright if callable(cright) else (lambda u, v: cright), obj)
    top(x, y, x + w, y + d, z + h, ctop if callable(ctop) else (lambda a, b: ctop), obj)
    return obj

# ---------- 建筑 ----------
LIT = hexc("#ffd877")
def rnd(*k):
    return (hash(k) & 0xffff) / 0xffff

def building(x, y, w, d, h, color, kind="grid", broken=None, damage=0, equip=True):
    # damage ≥ 1：约 30% 窗户碎成深色；equip=False：不画楼顶设备和天线（用于缺口里露出的内层）
    base = night(hexc(color))
    l, r, t = base, shade(base, -0.24), shade(base, 0.22)
    glass_l, glass_r = shade(base, -0.5), shade(base, -0.58)
    shard = night(hexc("#24262d"))
    def facade(face_col, glass, seed):
        def f(u, v):
            iu, iv = int(u), int(v)
            if broken and v > broken(u, seed):
                return None
            if v < 3 or v > h - 3:
                return face_col
            if kind == "grid":
                cu, cv = iu % 4, (iv - 3) % 6
                if cu in (1, 2) and 1 <= cv <= 3 and 1 < u < (w if seed == 0 else d) - 1:
                    if damage and rnd(x, y, seed, iu // 4, iv // 6, 7) < 0.3:
                        return shade(shard, 0.25) if (cu == 2 and cv == 3) else shard
                    if NIGHT and rnd(x, y, seed, iu // 4, iv // 6) < 0.38:
                        return LIT if cv > 1 else shade(LIT, 0.3)
                    return shade(glass, 0.35) if (cu == 1 and cv == 1) else glass
                if cv == 0:
                    return shade(face_col, -0.06)
                return face_col
            # glass 塔：竖条玻璃 + 斜向反光
            cu = iu % 3
            if cu == 0:
                return shade(face_col, 0.08)
            refl = 0 < (u + v * 0.55) - (h * 0.55) < 5 or 0 < (u + v * 0.55) - (h * 0.25) < 2
            if damage and rnd(x, y, seed, iu // 3, iv // 4, 7) < 0.3:
                return shard
            if NIGHT and rnd(x, y, seed, iu // 3, iv // 4) < 0.3:
                return LIT
            return shade(glass, 0.45) if refl else glass
        return f
    obj = new_obj()
    left(x, x + w, y + d, 0, h, facade(l, glass_l, 0), obj)
    right(x + w, y, y + d, 0, h, facade(r, glass_r, 1), obj)
    if broken:
        return obj
    # 楼顶：外圈女儿墙亮，内部略暗
    def roof(a, b):
        rim = a < x + 1.2 or b < y + 1.2 or a > x + w - 1.2 or b > y + d - 1.2
        return t if rim else shade(t, -0.12)
    top(x, y, x + w, y + d, h, roof, obj)
    if not equip:
        return obj
    # 楼顶设备
    box(x + 2, y + 2, h, 5, 4, 3, shade(t, 0.1), shade(l, 0.1), shade(r, 0.1))
    if w > 14:
        box(x + w - 7, y + d - 7, h, 4, 4, 2, shade(t, -0.05), shade(l, 0.05), r)
    if h > 70:
        ax, ay = P(x + w / 2, y + d / 2, h)
        aid = new_obj()
        for k in range(14):
            plot(int(ax), int(ay) - k, x + y + w + d + h + 2, hexc("#5b616c"), aid, 4)
        if NIGHT:
            plot(int(ax), int(ay) - 14, x + y + w + d + h + 3, hexc("#ff5252"), aid, 4)
    return obj

# ---------- 萌系圆球精灵 ----------
LIGHT = np.array([-0.55, -0.65, 0.52]); LIGHT /= np.linalg.norm(LIGHT)

class Sprite:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.c = np.zeros((h, w, 4))
        self.part = np.zeros((h, w), dtype=int)
        self.n = 0
    def blob(self, cx, cy, rx, ry, pal, clip=None):
        # pal: [高光, 亮, 中, 暗]，按法线与光照分四档
        self.n += 1
        for yy in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for xx in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = (xx + 0.5 - cx) / rx, (yy + 0.5 - cy) / ry
                r2 = dx * dx + dy * dy
                if r2 > 1 or not (0 <= xx < self.w and 0 <= yy < self.h):
                    continue
                if clip and not clip(xx, yy):
                    continue
                nz = math.sqrt(1 - r2)
                k = dx * LIGHT[0] + dy * LIGHT[1] + nz * LIGHT[2]
                c = pal[0] if k > 0.86 else pal[1] if k > 0.55 else pal[2] if k > 0.12 else pal[3]
                self.c[yy, xx] = c
                self.part[yy, xx] = self.n
    def dot(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c[y, x] = c
            self.part[y, x] = 999
    def rect(self, x0, y0, x1, y1, c):
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                self.dot(xx, yy, c)
    def eye(self, cx, cy, rx=2.6, ry=3.4):
        for yy in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for xx in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = (xx + 0.5 - cx) / rx, (yy + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1:
                    self.dot(xx, yy, hexc("#1a1c26"))
        self.rect(int(cx - rx + 1), int(cy - ry + 1), int(cx - rx + 3), int(cy - ry + 3), hexc("#ffffff"))
        self.dot(int(cx + rx - 1), int(cy + ry - 2), hexc("#ffffff"))
    def outline(self):
        a = self.c[:, :, 3] > 0
        out = self.c.copy()
        for yy in range(self.h):
            for xx in range(self.w):
                if a[yy, xx]:
                    # 内部不同部件交界处画柔和分界线
                    for dx, dy in ((1, 0), (0, 1)):
                        nx, ny = xx + dx, yy + dy
                        if nx < self.w and ny < self.h and a[ny, nx] and self.part[ny, nx] != self.part[yy, xx] \
                                and self.part[yy, xx] != 999 and self.part[ny, nx] != 999 and self.part[ny, nx] < self.part[yy, xx]:
                            out[ny, nx] = shade(self.c[ny, nx], -0.22)
                    continue
                nb = [self.c[yy + dy, xx + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                      if 0 <= xx + dx < self.w and 0 <= yy + dy < self.h and a[yy + dy, xx + dx]]
                if nb:
                    dark = min(nb, key=lambda c: c[0] + c[1] + c[2])
                    out[yy, xx] = shade(dark, -0.62)
        self.c = out
    def place(self, wx, wy, wz=0.0, flip=False):
        # 精灵脚底中点对准世界坐标；深度按脚底 + 高度
        sx0, sy0 = P(wx, wy, wz)
        obj = new_obj()
        for yy in range(self.h):
            for xx in range(self.w):
                c = self.c[yy, xx if not flip else self.w - 1 - xx]
                if c[3] == 0:
                    continue
                up = self.h - 1 - yy
                plot(int(sx0 - self.w / 2 + xx), int(sy0 - self.h + 1 + yy), wx + wy + wz + up * 0.5 + 6, c, obj, 4)

def sprite_png(path):
    # 读入像素化后的 AI 精灵帧
    im = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    sp = Sprite(im.shape[1], im.shape[0])
    sp.c = im
    if NIGHT:
        sp.c[:, :, :3] *= 0.78
    return sp

def pal(h):
    b = night(hexc(h), -0.15)
    return [shade(b, 0.45), shade(b, 0.18), b, shade(b, -0.32)]

def lizard():
    s = Sprite(64, 66)
    skin, belly, fin = pal("#4a6b78"), pal("#b9d3c8"), pal("#8fe3ff" if NIGHT else "#9fd6e6")
    s.blob(14, 52, 13, 7, skin)                 # 尾巴
    s.blob(5, 49, 5, 4, skin)
    for (fx, fy, rx, ry) in [(15, 9, 4, 5), (10, 18, 4.5, 5.5), (8, 29, 4.5, 5.5), (8, 40, 4, 5), (8, 50, 3.5, 4.2)]:
        s.blob(fx, fy, rx, ry, fin)             # 背鳍（圆角，从背后露出）
    s.blob(30, 47, 14, 14, skin)                # 身体
    s.blob(34, 50, 8, 9, belly)                 # 肚皮
    s.blob(24, 61, 6, 4.5, skin)                # 脚
    s.blob(38, 61, 6, 4.5, skin)
    s.blob(44, 42, 4.5, 4, skin)                # 小手
    s.blob(33, 24, 17, 15, skin)                # 大头
    s.blob(45, 29, 8, 6.5, skin)                # 吻部
    s.blob(24, 8, 2.5, 3.5, fin); s.blob(31, 6, 2.5, 3.5, fin)   # 头顶小角
    s.eye(35, 22); s.eye(45, 22)
    # 腮红 + 小嘴 + 牙
    s.rect(29, 28, 32, 30, hexc("#ff9fb2")); s.rect(47, 28, 50, 30, hexc("#ff9fb2"))
    s.rect(40, 31, 46, 32, hexc("#2b2f3a")); s.dot(42, 32, hexc("#ffffff"))
    s.outline()
    return s

def ape():
    s = Sprite(60, 62)
    fur, face, dark = pal("#7a5238"), pal("#e8c39e"), pal("#5a3a28")
    s.eye = Sprite.eye.__get__(s)
    s.blob(12, 40, 6, 13, fur)                  # 长手臂（后）
    s.blob(30, 44, 15, 14, fur)                 # 身体
    s.blob(31, 47, 8, 8, face)                  # 胸口
    s.blob(22, 58, 6, 4, dark)                  # 脚
    s.blob(38, 58, 6, 4, dark)
    s.blob(49, 42, 6, 12, fur)                  # 长手臂（前）
    s.blob(50, 54, 5.5, 4.5, dark)              # 拳头
    s.blob(12, 52, 5, 4, dark)
    s.blob(16, 20, 4.5, 5, fur)                 # 耳朵
    s.blob(46, 20, 4.5, 5, fur)
    s.blob(31, 21, 16, 15, fur)                 # 大头
    s.blob(31, 25, 11, 9, face)                 # 脸
    s.blob(31, 30, 7, 4.5, face)                # 嘴部
    s.eye(26, 22, 2.4, 3.1); s.eye(36, 22, 2.4, 3.1)
    s.rect(29, 28, 31, 29, hexc("#3a2418")); s.rect(32, 28, 34, 29, hexc("#3a2418"))   # 鼻孔
    s.rect(27, 32, 36, 33, hexc("#3a2418"))
    s.rect(21, 27, 24, 29, hexc("#ff9f9f")); s.rect(38, 27, 41, 29, hexc("#ff9f9f"))
    s.outline()
    return s

def puff(cx, cy, scale=1.0, smoke=False):
    # smoke=True：楼顶冒的灰烟；否则为浅色尘土
    s = Sprite(int(30 * scale) + 4, int(22 * scale) + 4)
    if smoke:
        c = pal("#b4aea6" if not NIGHT else "#6d6862")
    else:
        c = pal("#efe4cf" if not NIGHT else "#8a8378")
    for (x, y, r) in [(9, 14, 7), (19, 13, 8), (14, 8, 7), (24, 16, 5.5)]:
        s.blob(x * scale + 2, y * scale + 2, r * scale, r * scale * 0.9, c)
    s.outline()
    return s

# ---------- 场景 ----------
S, T = 176, 16
wx0, wy0 = 40, 126        # 海区（前左角）：x∈[wx0, S-40)，y ≥ wy0
RX, RY = 80, 76           # 竖路 x∈[RX, RX+16)（只到海边），横路 y∈[RY, RY+16)
PID = [0]                 # 底座顶面物体编号（不描边）

# 8 个楼位：(x, y, w, d, h, 颜色, 外立面)；顺序即 space 顺序。四个街区，楼间至少隔 8
SLOTS = [
    (8, 8, 24, 24, 120, "#6f8fc9", "grid"),
    (104, 44, 24, 20, 136, "#e07a3c", "grid"),
    (40, 42, 22, 22, 90, "#5fae6e", "grid"),
    (144, 40, 22, 22, 100, "#ddd5c1", "grid"),
    (46, 8, 20, 20, 72, "#d9573f", "grid"),
    (104, 4, 28, 28, 190, "#a3acbd", "glass"),
    (10, 100, 20, 14, 48, "#d8a548", "grid"),
    (106, 100, 22, 14, 40, "#c87fb0", "grid"),
]
# 怪兽出场 / 退场的海边入场点（世界坐标，水面 z=-4）
ENTRY = (88, 150)
# 天空里的云（屏幕坐标中心、大小）
CLOUDS = [(70, 60, 1.3), (330, 40, 1.0), (360, 150, 0.8), (110, 170, 0.7)]

def draw_plate():
    gnd = night(hexc("#d4cfc5"))
    side = night(hexc("#a39d92"))

    def ground(x, y):
        if wx0 <= x < S - 40 and y >= wy0:
            return None
        on_road_x = RY <= y < RY + 16
        on_road_y = RX <= x < RX + 16 and y < wy0
        if on_road_x or on_road_y:
            c = night(hexc("#4b4f57"))
            if on_road_x and RY + 7.5 <= y < RY + 8.5 and int(x) % 10 < 5 and not RX - 2 <= x < RX + 18:
                return night(hexc("#f1f1f1"))
            if on_road_y and RX + 7.5 <= x < RX + 8.5 and int(y) % 10 < 5 and not RY - 4 <= y < RY + 20:
                return night(hexc("#f1f1f1"))
            # 斑马线
            if on_road_x and RX - 7 <= x < RX - 2 and int(y) % 3 == 0:
                return night(hexc("#eeeeee"))
            if on_road_x and RX + 18 <= x < RX + 23 and int(y) % 3 == 0:
                return night(hexc("#eeeeee"))
            return c
        # 人行道边缘（贴路一圈浅色路沿）
        near = (RY - 3 <= y < RY) or (RY + 16 <= y < RY + 19) or \
               (RX - 3 <= x < RX and y < wy0) or (RX + 16 <= x < RX + 19 and y < wy0)
        if near:
            return shade(gnd, 0.12)
        # 地砖缝
        if int(x) % 8 == 0 or int(y) % 8 == 0:
            return shade(gnd, -0.05)
        return gnd

    pid = PID[0] = new_obj()
    # 底座侧面：上沿浅色混凝土 + 深色土层 + 底线
    def slab_side(col):
        def f(u, v):
            if v > T - 3:
                return shade(col, 0.15)
            if v < 2:
                return hexc("#2c2724")
            if rnd(int(u), int(v)) < 0.08:
                return shade(col, -0.45)
            return shade(col, -0.32)
        return f
    left(0, wx0, S, -T, 0, slab_side(side), pid)
    left(S - 40, S, S, -T, 0, slab_side(side), pid)
    right(S, 0, S, -T, 0, slab_side(shade(side, -0.12)), pid)
    top(0, 0, S, S, 0, ground, pid)

    # 海：水面 z=-4，剖面渐变 + 浪花
    water = night(hexc("#3c9fe6"), -0.3)
    wid = new_obj()
    def wtop(x, y):
        if y < wy0 + 3 + 2 * math.sin(x * 0.5):
            return shade(water, 0.85)
        if int(y) % 6 == 0 and rnd(int(x / 4), int(y)) < 0.35:
            return shade(water, 0.6)
        return water if int(y) % 12 < 6 else shade(water, 0.06)
    top(wx0, wy0, S - 40, S, -4, wtop, wid)
    def wside(u, v):
        k = v / (T - 4)
        c = shade(water, -0.45 + 0.4 * k)
        if v > T - 6:
            return shade(water, 0.55) if int(u) % 4 else shade(water, 0.2)
        return c
    left(wx0, S - 40, S, -T, -4, wside, wid)
    # 岸墙
    left(wx0, S - 40, wy0, -4, 0, lambda u, v: shade(side, -0.1), new_obj())
    right(wx0, wy0, S, -4, 0, lambda u, v: shade(side, -0.25), new_obj())
    right(S - 40, wy0, S, -4, 0, lambda u, v: shade(side, -0.1), new_obj())

    # 树、小车
    for (tx, ty) in [(36, 70), (70, 38), (70, 68), (138, 70), (170, 70), (36, 104), (140, 106), (166, 118), (100, 70)]:
        t = Sprite(9, 12)
        t.rect(4, 8, 5, 12, hexc("#6b4a33"))
        t.blob(4.5, 5, 4.2, 4.2, pal("#55b06a"))
        t.outline()
        t.place(tx, ty)
    for (cx, cy, col) in [(22, 79, "#e8463b"), (52, 86, "#f2c14e"), (83, 30, "#4a8fe8"), (90, 52, "#ffffff"),
                          (146, 79, "#3fb07a"), (83, 104, "#e8463b")]:
        horiz = RY <= cy < RY + 16
        w_, d_ = (6, 3) if horiz else (3, 6)
        c0 = night(hexc(col), -0.25)
        box(cx, cy, 0, w_, d_, 2, shade(c0, 0.2), c0, shade(c0, -0.25))
        box(cx + (1 if horiz else 0.5), cy + (0.5 if horiz else 1), 2, w_ - 2 if horiz else 2, d_ - 1 if horiz else d_ - 2, 1.5,
            hexc("#bfe3ff") if not NIGHT else hexc("#ffe39a"), hexc("#7fa6c4"), hexc("#6a8aa3"))

def clouds():
    # 天空里的像素云（RGBA 图层，屏幕坐标）
    img = np.zeros((H, W, 4), dtype=np.uint8)
    for (cx, cy, k) in CLOUDS:
        sp = Sprite(int(46 * k) + 6, int(22 * k) + 6)
        c = pal("#ffffff") if not NIGHT else pal("#5a6273")
        for (x, y, r) in [(12, 14, 8), (24, 11, 10), (36, 14, 8), (19, 16, 7), (30, 17, 7)]:
            sp.blob(x * k + 3, y * k + 3, r * k, r * k * 0.8, c)
        sp.outline()
        arr = np.clip(sp.c, 0, 255).astype(np.uint8)
        # 云的描边改浅，避免太重
        dark = (arr[:, :, 3] > 0) & (arr[:, :, :3].sum(axis=2) < (380 if not NIGHT else 150))
        arr[dark, :3] = (np.array([200, 205, 214]) if not NIGHT else np.array([40, 45, 56]))
        x0, y0 = int(cx - sp.w / 2), int(cy - sp.h / 2)
        m = arr[:, :, 3] > 0
        img[y0:y0 + sp.h, x0:x0 + sp.w][m] = arr[m]
    return img

def rubble(x0, y0, x1, y1, n, colors, seed, hmax=3):
    # 在 [x0,x1)×[y0,y1) 内撒 n 块小碎石
    for k in range(n):
        rx = x0 + rnd(seed, k, 1) * (x1 - x0 - 2)
        ry = y0 + rnd(seed, k, 2) * (y1 - y0 - 2)
        c = night(hexc(colors[k % len(colors)]))
        bw, bd = 1.5 + int(rnd(seed, k, 3) * 3), 1.5 + int(rnd(seed, k, 4) * 3)
        box(rx, ry, 0, bw, bd, 1 + int(rnd(seed, k, 5) * hmax), shade(c, 0.2), c, shade(c, -0.3))

def draw_slot(i, damage):
    # damage：0 完好 / 1 轻损（碎窗+冒烟）/ 2 重损（顶部锯齿缺口）/ 3 废墟 / -1 空地
    x, y, w, d, h, color, kind = SLOTS[i]
    if damage < 0:
        dirt = night(hexc("#bdb6aa"))
        top(x + 2, y + 2, x + w - 2, y + d - 2, 0, lambda a, b: shade(dirt, -0.06) if rnd(int(a), int(b), 9) < 0.2 else dirt,
            new_obj(), bias=0.01)
        rubble(x + 3, y + 3, x + w - 3, y + d - 3, 5, ["#9a8f84", "#b3aaa0"], i * 31)
        return
    if damage <= 1:
        building(x, y, w, d, h, color, kind, damage=damage)
        if damage == 1:
            puff(0, 0, 0.55, smoke=True).place(x + w * 0.6, y + d * 0.4, h)
        return
    if damage == 2:
        lo = max(10, round(h * 0.62))
        jag = lambda u, seed: lo + 2 + h * 0.12 * abs(math.sin(u * 0.45 + seed)) + (h * 0.14 if u < w * 0.4 else 0)
        building(x, y, w, d, h, color, kind, broken=jag, damage=1)
        building(x, y, w, d, lo, color, kind, damage=1, equip=False)
        puff(0, 0, 0.7, smoke=True).place(x + w * 0.5, y + d * 0.5, lo)
        return
    # 废墟：≤12 高的残墙 + 碎石堆
    wall = min(12, h)
    building(x, y, w, d, wall, color, kind, broken=lambda u, seed: 4 + 8 * abs(math.sin(u * 0.6 + seed * 2.1)), damage=1)
    building(x, y, w, d, 3, color, kind, equip=False)
    rubble(x - 2, y - 2, x + w + 3, y + d + 3, 18, [color, "#9a8f84", color, "#b3aaa0"], i * 17 + 3, hmax=4)

def finish():
    # 建筑类描边与高光（矢量化）：与后方物体或空白相邻 → 深色描边；顶/侧交界、左右竖棱 → 提亮
    out = COL.copy()
    o = OBJ
    pad_o = np.pad(o, 1)
    pad_d = np.pad(DEP, 1, constant_values=-1e9)
    edge = np.zeros_like(o, dtype=bool)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        o2 = pad_o[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
        d2 = pad_d[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
        edge |= (o2 == 0) | ((o2 != o) & (d2 < DEP - 2))
    inner = np.zeros_like(edge)
    inner[1:-1, 1:-1] = True
    cand = inner & (o != 0) & (FACE != 4)
    m_edge = cand & edge
    m_line = m_edge & (o != PID[0])
    out[m_line, :3] = COL[m_line, :3] * 0.45
    rest = cand & ~m_edge
    f_dn = np.zeros_like(FACE); f_dn[:-1] = FACE[1:]
    o_dn = np.zeros_like(o); o_dn[:-1] = o[1:]
    m_top = rest & (FACE == 1) & ((f_dn == 2) | (f_dn == 3)) & (o_dn == o)
    out[m_top, :3] = COL[m_top, :3] + (255 - COL[m_top, :3]) * 0.35
    f_rt = np.zeros_like(FACE); f_rt[:, :-1] = FACE[:, 1:]
    o_rt = np.zeros_like(o); o_rt[:, :-1] = o[:, 1:]
    m_rt = rest & (FACE == 2) & (f_rt == 3) & (o_rt == o)
    out[m_rt, :3] = COL[m_rt, :3] + (255 - COL[m_rt, :3]) * 0.2
    return np.clip(out, 0, 255).astype(np.uint8)

def layer(objs=None):
    # 导出 RGBA 图层；objs 为物体编号区间 (lo, hi) 时只保留这些物体的可见像素
    out = finish()
    if objs is not None:
        lo, hi = objs
        keep = (OBJ >= lo) & (OBJ < hi)
        out[~keep] = 0
    return out

def shadow():
    # 底座投影（半透明），作为 plate 的最底层
    corners = [P(-4, -4, -T), P(S + 10, -4, -T), P(S + 10, S + 10, -T), P(-4, S + 10, -T)]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(x + 4, y + 6) for x, y in corners], fill=(0, 0, 0, 34 if not NIGHT else 110))
    return img

def stage_color():
    return "#0e1117" if NIGHT else "#f5f5f4"

def main():
    # 整幅样张：天空 + 底座 + 8 楼（橙楼重损）+ 可选怪兽（SPRITES="路径:x:y;..." 世界坐标）
    out_dir = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "day"
    scale = 2
    reset(mode)
    draw_plate()
    for i in range(len(SLOTS)):
        draw_slot(i, 2 if i == 1 else 0)
    for item in filter(None, os.environ.get("SPRITES", "").split(";")):
        path, sx_, sy_ = item.rsplit(":", 2)
        sprite_png(path).place(float(sx_), float(sy_))
    stage = Image.new("RGBA", (W, H), tuple(hexc(stage_color()).astype(int)))
    stage.alpha_composite(Image.fromarray(clouds(), "RGBA"))
    stage.alpha_composite(shadow())
    stage.alpha_composite(Image.fromarray(layer(), "RGBA"))
    stage.resize((W * scale, H * scale), Image.NEAREST).save(f"{out_dir}/render-{mode}.png")
    print("ok", mode)

if __name__ == "__main__":
    main()
