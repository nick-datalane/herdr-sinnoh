# AI 动作表 → 像素精灵帧
# 用法：python3 -I art/pixelize.py <动作表.png> <输出目录> [目标高度=56] [颜色数=20] [--poses N]
# 步骤：去白底 → 按列间空白切出每个姿势 → 统一缩放到目标高度 → 统一调色板 → 1 像素描边
import os, sys
import numpy as np
from PIL import Image

# 位置参数（去掉 --native、--poses N 这类选项）
pos = [a for i, a in enumerate(sys.argv) if not a.startswith("--") and sys.argv[i - 1] != "--poses"]
src, out = pos[1], pos[2]
TARGET_H = int(pos[3]) if len(pos) > 3 else 56
COLORS = int(pos[4]) if len(pos) > 4 else 32
# 源图本身是像素画时：按像素格中心直接取色、不额外描边（--native）
NATIVE = "--native" in sys.argv
os.makedirs(out, exist_ok=True)

im = Image.open(src).convert("RGB")
a = np.asarray(im).astype(int)
# 白底判定：接近白色且低饱和
bright = a.min(axis=2)
spread = a.max(axis=2) - a.min(axis=2)
white = (bright > 232) & (spread < 18)
# 只有从图片边缘连通过来的白色才是背景（角色身上被描边围住的白毛、白肚皮、高光保留）
from PIL import ImageDraw
wm = Image.fromarray((white * 255).astype(np.uint8)).copy()
H_, W_ = white.shape
for x, y in [(x, 0) for x in range(W_)] + [(x, H_ - 1) for x in range(W_)] + [(0, y) for y in range(H_)] + [(W_ - 1, y) for y in range(H_)]:
    if wm.getpixel((x, y)) == 255:
        ImageDraw.floodfill(wm, (x, y), 128)
fg = np.array(wm) != 128

# 按列切：连续前景列构成一个姿势，间隙不超过 gap 的合并
cols = fg.sum(axis=0) > max(2, fg.shape[0] * 0.004)

def split(gap):
    spans, start, blank = [], None, 0
    for x, on in enumerate(cols):
        if on:
            if start is None:
                start = x
            blank = 0
        elif start is not None:
            blank += 1
            if blank > gap:
                spans.append((start, x - blank))
                start, blank = None, 0
    if start is not None:
        spans.append((start, len(cols) - 1))
    return [s for s in spans if s[1] - s[0] > im.width * 0.03]

# --poses N：已知姿势数时，间隙阈值自动调整到正好切出 N 段（姿势间空白很窄、或姿势内部有空隙都能处理）
POSES = int(sys.argv[sys.argv.index("--poses") + 1]) if "--poses" in sys.argv else None
gap = max(8, im.width // 120)
spans = split(gap)
if POSES and len(spans) != POSES:
    # 段数不对时，间隙阈值从默认值往两边找（太多段 → 调大合并，太少段 → 调小切开）
    for g in sorted(range(0, 120), key=lambda g: abs(g - gap)):
        if len(split(g)) == POSES:
            gap, spans = g, split(g)
            break

# 每个姿势的上下边界
boxes = []
for x0, x1 in spans:
    rows = np.where(fg[:, x0:x1 + 1].sum(axis=1) > 0)[0]
    boxes.append((x0, rows.min(), x1 + 1, rows.max() + 1))
if not boxes:
    sys.exit("没找到姿势")

# 统一缩放比例：以最高姿势对齐目标高度，保证各帧角色大小一致
hmax = max(b[3] - b[1] for b in boxes)
k = TARGET_H / hmax

frames = []
for (x0, y0, x1, y1) in boxes:
    crop = im.crop((x0, y0, x1, y1))
    mask = Image.fromarray((fg[y0:y1, x0:x1] * 255).astype(np.uint8))
    w, h = max(1, round((x1 - x0) * k)), max(1, round((y1 - y0) * k))
    small = crop.resize((w, h), Image.NEAREST if NATIVE else Image.BOX)
    m = np.asarray(mask.resize((w, h), Image.BOX)) > 110
    frames.append((small, m))

# 统一调色板：所有帧拼起来一起量化
strip_w = sum(f[0].width for f in frames)
strip = Image.new("RGB", (strip_w, TARGET_H), (255, 255, 255))
x = 0
for s, m in frames:
    strip.paste(s, (x, TARGET_H - s.height)); x += s.width
pal_img = strip.quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE if NATIVE else Image.Quantize.MEDIANCUT)

for i, (s, m) in enumerate(frames):
    q = np.asarray(s.quantize(palette=pal_img, dither=Image.Dither.NONE).convert("RGB")).astype(int)
    rgba = np.zeros((s.height + 2, s.width + 2, 4), dtype=np.uint8)
    rgba[1:-1, 1:-1, :3] = q
    rgba[1:-1, 1:-1, 3] = np.where(m, 255, 0)
    # 1 像素描边：透明像素挨着角色 → 取相邻最暗色再压暗
    al = rgba[:, :, 3] > 0
    outl = rgba.copy()
    if NATIVE:
        # 清掉白底残留：紧邻透明区的近白像素删掉，两遍
        for _ in range(2):
            al = outl[:, :, 3] > 0
            rgb = outl[:, :, :3].astype(int)
            whiteish = (rgb.min(axis=2) > 200) & (rgb.max(axis=2) - rgb.min(axis=2) < 40)
            pad = np.pad(~al, 1, constant_values=True)
            near = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
            outl[al & whiteish & near, 3] = 0
        Image.fromarray(outl, "RGBA").save(f"{out}/frame{i}.png")
        continue
    for yy in range(rgba.shape[0]):
        for xx in range(rgba.shape[1]):
            if al[yy, xx]:
                continue
            nb = [rgba[yy + dy, xx + dx, :3] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= yy + dy < rgba.shape[0] and 0 <= xx + dx < rgba.shape[1] and al[yy + dy, xx + dx]]
            if nb:
                c = min(nb, key=lambda c: int(c[0]) + int(c[1]) + int(c[2])).astype(float) * 0.45
                outl[yy, xx] = [*c.astype(np.uint8), 255]
    Image.fromarray(outl, "RGBA").save(f"{out}/frame{i}.png")
print(f"{len(frames)} frames, height {TARGET_H}, scale {k:.4f}")
