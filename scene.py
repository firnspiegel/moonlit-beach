"""月光海滩: Claude 娘和 Clawd 坐在沙滩上看海 (像素风, 侧后方 30° 视角)。

背景画布 512x320, 放大 5 倍 = 2560x1600; 人物在 chars_hd.py, 2.5 倍精度。
python scene.py preview [B] [C]   -> preview_B.png / preview_C.png (第 0 帧)
python scene.py gif [B] [C]       -> beach_B.gif / beach_C.gif (24 帧)
B = 上色版, C = 逆光剪影版; 不写默认两个都出。
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 512, 320
SCALE = 5
N = 24            # 帧数 (一个海浪周期)
FRAME_MS = 120
HORIZON = 138
SHORE = 212       # 海浪最远退到这里

HERE = Path(__file__).resolve().parent
TAU = math.tau


def c(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def dither_pick(colors, t, x, y):
    """t in [0,1] 沿 colors 渐变, 用 4x4 Bayer 抖动取色。"""
    t = max(0.0, min(1.0, t)) * (len(colors) - 1)
    i = int(t)
    if i >= len(colors) - 1:
        return colors[-1]
    frac = t - i
    return colors[i + 1] if frac * 16 > BAYER[y & 3][x & 3] + 0.5 else colors[i]


# ---------------- 调色板 ----------------
SKY = [c(h) for h in ("#04071A", "#070C22", "#0A112A", "#0E1733", "#131E3D", "#1A2747")]
HALO = [c("#1D2A4E"), c("#24325A")]
MOON = c("#E4E0CA")
MOON_SHADE = c("#CFCAB2")
MOON_EDGE = c("#BDB8A2")
STAR = [c("#4A5478"), c("#8890B4"), c("#D6DAEE")]
SEA = [c(h) for h in ("#1C2949", "#16223F", "#111C36", "#0E172E", "#0C1429")]
RIPPLE = c("#23315A")
GLINT = [c("#5E6A92"), c("#9AA2C0"), c("#D9D6C6")]
SHALLOW = c("#1B2C4C")
FOAM = [c("#7D8AA8"), c("#BAC3D6"), c("#E0E4EC")]
SAND = [c(h) for h in ("#302A42", "#2A253B", "#241F33", "#1D1A2B", "#17141F")]
WET = c("#1F1C30")
SHADOW = c("#15121E")

# Claude 娘 (月光下, 偏冷偏暗)
HAIR = c("#A9533A")
HAIR_DK = c("#713227")
HAIR_DKK = c("#4A221D")
HAIR_HI = c("#D9824F")
HAIR_RIM = c("#F0A86E")
SKIN = c("#D7B8AA")
SKIN_DK = c("#A88A82")
CREAM = c("#BFB7A6")
CREAM_DK = c("#8C8576")
CREAM_HI = c("#DCD5C4")
ORANGE = c("#B4613A")
BLACK = c("#16131B")
GOLD = c("#B08A42")
FLOWER = c("#D2743E")
FLOWER_HI = c("#EE9C5E")
FLOWER_C = c("#7C3420")
LASH = c("#2A1A1C")

# Clawd
CL_BACK = c("#A6563F")
CL_BACK_DK = c("#86432F")
CL_SIDE = c("#C96D50")
CL_RIM = c("#EC9A74")


rnd = random.Random(7)
STARS = []
while len(STARS) < 90:
    x, y = rnd.randrange(W), rnd.randrange(HORIZON - 8)
    if (x - 404) ** 2 + (y - 58) ** 2 < 40 ** 2:
        continue
    STARS.append((x, y, rnd.random(), rnd.choice([1, 1, 1, 2]), rnd.random() < 0.08))

RIPPLES = [(rnd.randrange(W), rnd.randrange(HORIZON + 3, SHORE - 2), rnd.randrange(3, 14), rnd.random())
           for _ in range(140)]
SPECKS = [(rnd.randrange(W), rnd.randrange(SHORE, H), rnd.random()) for _ in range(700)]
FOAM_NOISE = [rnd.uniform(-1.2, 1.2) for _ in range(W)]


def osc(f, k=1, ph=0.0):
    """以 N 帧为周期循环的 0..1 振荡。"""
    return 0.5 - 0.5 * math.cos(TAU * (k * f / N + ph))


# ---------------- 背景 ----------------
def draw_background(px, f):
    # 天空 + 月晕
    for y in range(HORIZON):
        for x in range(W):
            col = dither_pick(SKY, y / (HORIZON - 1), x, y)
            d = math.hypot(x - 404, y - 58)
            if d < 46:
                t = 1 - (d - 16) / 30
                if t > 0:
                    col = dither_pick([col, HALO[0], HALO[1]], t * 0.9, x, y)
            px[x, y] = col

    # 星星
    for x, y, ph, kind, big in STARS:
        b = osc(f, 1 if kind == 1 else 2, ph)
        level = 0 if b < 0.35 else (1 if b < 0.8 or not big else 2)
        if kind == 2:
            level = min(2, level + 1)
        px[x, y] = STAR[level]
        if big and b > 0.75:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                px[x + dx, y + dy] = STAR[0]

    # 月亮
    for y in range(58 - 16, 58 + 17):
        for x in range(404 - 16, 404 + 17):
            d = math.hypot(x - 404, y - 58)
            if d <= 15.5:
                col = MOON if d < 14.3 else MOON_EDGE
                px[x, y] = col
    for cx, cy, r in ((399, 53, 3.2), (409, 63, 2.4), (408, 51, 1.6), (397, 63, 1.8), (412, 57, 1.2)):
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if math.hypot(x - cx, y - cy) <= r:
                    px[x, y] = MOON_SHADE

    # 海
    for y in range(HORIZON, SHORE + 14):
        for x in range(W):
            px[x, y] = dither_pick(SEA, (y - HORIZON) / (SHORE - HORIZON), x, y)
    for x0, y, ln, ph in RIPPLES:
        if osc(f, 1, ph) > 0.45:
            for x in range(x0, min(W, x0 + ln)):
                px[x, y] = RIPPLE

    # 月光倒影: 一条闪烁的光带
    for y in range(HORIZON + 1, SHORE + 2, 2):
        depth = (y - HORIZON) / (SHORE - HORIZON)
        half = 4 + depth * 26
        for x in range(int(404 - half), int(404 + half) + 1):
            u = (x - 404) / half
            wv = math.sin(x * 0.55 + y * 1.7 + TAU * f / N * 2) + 0.6 * math.sin(x * 0.21 - y * 0.9 - TAU * f / N)
            v = wv - abs(u) * 1.8 + 0.5 - depth * 0.5
            if v > 0.2:
                px[x, y] = GLINT[2] if v > 1.15 and abs(u) < 0.35 else GLINT[1] if v > 0.7 else GLINT[0]

    # 一道涌向岸边的浪
    by = 186 + 26 * (f / N)
    fade = math.sin(math.pi * f / N)
    if fade > 0.15:
        for x in range(W):
            yy = int(by + 1.5 * math.sin(x * 0.04 + 1.3) + FOAM_NOISE[x] * 0.6)
            if (x * 7 + int(by)) % 11 < 9 * fade:
                px[x, yy] = FOAM[0] if fade < 0.6 else FOAM[1]

    # 沙滩
    for y in range(SHORE, H):
        for x in range(W):
            px[x, y] = dither_pick(SAND, (y - SHORE) / (H - SHORE), x, y)
    for x, y, v in SPECKS:
        r, g, b = px[x, y]
        d = 8 if v > 0.5 else -6
        px[x, y] = (max(0, r + d), max(0, g + d), max(0, b + d))

    # 海浪冲上沙滩又退回
    reach = SHORE + 3 + 11 * osc(f)
    wet_to = SHORE + 15
    for x in range(W):
        edge = reach + 1.6 * math.sin(x * 0.05 + 0.7) + 1.1 * math.sin(x * 0.13 + 2.0) + FOAM_NOISE[x]
        wet = wet_to + 1.6 * math.sin(x * 0.05 + 0.7) + FOAM_NOISE[x]
        for y in range(SHORE - 2, min(H, int(wet) + 1)):
            if y < edge - 1:
                px[x, y] = dither_pick([SHALLOW, SEA[-1]], (edge - y) / 10, x, y)
            elif y < edge + 1:
                px[x, y] = FOAM[2] if (x * 3 + f) % 5 else FOAM[1]
            elif y < wet:
                px[x, y] = WET


# ---------------- 角色 ----------------
def poly(d, pts, col):
    d.polygon([(round(x), round(y)) for x, y in pts], fill=col)


def draw_shadows(d):
    # 月光在右前方, 影子朝左下 (朝镜头) 拉长
    poly(d, [(200, 300), (250, 302), (286, 302), (262, 318), (186, 320), (170, 312)], SHADOW)
    poly(d, [(152, 296), (184, 297), (172, 307), (138, 307)], SHADOW)


def draw_clawd(d, f):
    ox, oy = 150, 279 + (1 if 10 <= f < 13 else 0)
    s = 2

    def r(x0, y0, x1, y1, col):
        d.rectangle([ox + x0 * s, oy + y0 * s, ox + (x1 + 1) * s - 1, oy + (y1 + 1) * s - 1], fill=col)

    r(3, 0, 14, 7, CL_BACK)          # 背面 (背光)
    r(3, 6, 14, 7, CL_BACK_DK)
    r(15, 0, 15, 7, CL_SIDE)         # 右侧面, 被月光照亮
    d.line([ox + 16 * s - 1, oy, ox + 16 * s - 1, oy + 8 * s - 1], fill=CL_RIM)
    lift = 1 if 16 <= f < 20 else 0  # 偶尔抬一下右手
    r(1, 4, 2, 5, CL_BACK_DK)        # 左手
    r(16, 4 - lift, 17, 5 - lift, CL_SIDE)
    d.line([ox + 18 * s - 1, oy + (4 - lift) * s, ox + 18 * s - 1, oy + (6 - lift) * s - 1], fill=CL_RIM)
    for lx in (4, 6, 11, 13):        # 四条小腿
        r(lx, 8, lx, 8, CL_BACK_DK if lx < 13 else CL_SIDE)


def draw_girl(d, px, f):
    sway = math.sin(TAU * f / N)

    def sw(y):
        return sway * max(0.0, (y - 262) / 50) * 2.0

    # 裙子铺在沙上
    poly(d, [(200, 302), (206, 292), (222, 289), (246, 290), (262, 294), (264, 303), (232, 308), (202, 308)], CREAM_DK)
    poly(d, [(202, 305), (263, 301), (263, 304), (232, 309), (201, 309)], BLACK)          # 黑色裙层
    poly(d, [(208, 308), (258, 305), (257, 307), (230, 310), (207, 310)], ORANGE)         # 橙色裙层
    for x in range(210, 258, 4):
        px[x, 307] = CREAM

    # 腿朝右前方 (朝海) 伸出去, 大半被身体挡住, 透视缩短
    poly(d, [(244, 292), (254, 289), (264, 287), (268, 292), (256, 296), (246, 298)], CREAM_DK)
    d.line([(248, 291), (256, 289), (264, 287)], fill=CREAM)
    poly(d, [(262, 287), (266, 286), (269, 291), (264, 293)], BLACK)                     # 裙摆黑边
    d.line([(264, 293), (269, 291)], fill=ORANGE)
    poly(d, [(267, 285), (272, 284), (274, 288), (269, 290)], CREAM)                     # 短靴
    poly(d, [(268, 290), (273, 289), (274, 292), (269, 293)], CREAM_DK)
    px[271, 286] = c("#6A4630")

    # 束腰 (两臂之间露出一点)
    poly(d, [(210, 276), (243, 276), (246, 292), (207, 292)], BLACK)
    px[243, 283] = GOLD
    px[243, 285] = GOLD

    # 左臂 (背光): 撑在身后左边的沙上
    poly(d, [(211, 262), (206, 265), (201, 277), (196, 289), (201, 291), (206, 281), (212, 270)], CREAM_DK)
    poly(d, [(195, 287), (201, 288), (201, 292), (195, 292)], BLACK)
    poly(d, [(193, 293), (200, 293), (201, 295), (193, 295)], SKIN_DK)
    # 右臂 (受光): 撑在身后右边的沙上
    poly(d, [(241, 262), (247, 264), (251, 275), (256, 288), (251, 290), (246, 280), (241, 270)], CREAM)
    d.line([(247, 264), (251, 275), (256, 288)], fill=CREAM_HI)
    d.line([(241, 270), (246, 280), (250, 289)], fill=c("#746C61"))
    poly(d, [(250, 287), (256, 286), (257, 291), (251, 291)], BLACK)
    poly(d, [(251, 292), (259, 292), (259, 294), (251, 294)], SKIN)

    # 披肩: 撑出肩线
    poly(d, [(207, 280), (206, 268), (209, 261), (216, 257), (236, 257), (243, 261), (246, 268), (246, 280)], CREAM_DK)
    poly(d, [(234, 257), (243, 261), (246, 268), (246, 280), (240, 280), (239, 266)], CREAM)
    d.line([(237, 257), (243, 261), (246, 268), (246, 279)], fill=CREAM_HI)
    for (x, y) in ((242, 271), (241, 272), (243, 272), (242, 273), (242, 272)):
        px[x, y] = ORANGE                                                                  # 披肩上的菊纹

    # 长发: 顺着后背垂下来, 铺在沙上
    left = [(218, 250), (217, 262), (216, 274), (214, 286), (210, 296), (203, 304), (196, 309)]
    bottom = [(204, 313), (218, 314), (232, 313), (242, 309), (247, 303)]
    right = [(242, 296), (239, 286), (237, 274), (236, 262), (235, 250)]
    poly(d, [(x + sw(y), y) for x, y in left + bottom + right], HAIR)
    strands = [(219, HAIR_DKK, -0.9), (222, HAIR_DK, -0.5), (225, HAIR_DKK, -0.1),
               (228, HAIR_DK, 0.3), (231, HAIR_DKK, 0.6), (234, HAIR_HI, 0.9)]
    for x0, col, spread in strands:
        pts = []
        for y in range(252, 312, 2):
            t = (y - 252) / 60
            x = x0 + spread * 16 * t ** 1.6 + 1.0 * math.sin(y * 0.25 + x0) + sw(y)
            pts.append((round(x), y))
        for a, b in zip(pts, pts[1:]):
            d.line([a, b], fill=col)
    for (x, y) in right:                                   # 右边缘月光亮边
        px[round(x + sw(y)) - 1, y] = HAIR_RIM
    for y in range(252, 300):
        xr = 235.5 + max(0, y - 280) * 0.35 + sw(y)
        px[round(xr), y] = HAIR_RIM if y < 276 else HAIR_HI

    # 头
    d.ellipse([213, 231, 239, 257], fill=HAIR)
    d.arc([215, 232, 237, 250], 200, 330, fill=HAIR_HI)     # 头顶反光
    for x in range(217, 236, 2):                            # 编发
        px[x, 238] = HAIR_DK
        px[x + 1, 239] = HAIR_DKK
    d.line([(226, 240), (225, 247), (226, 256)], fill=HAIR_DK)
    d.line([(220, 242), (218, 250), (219, 257)], fill=HAIR_DK)
    d.line([(232, 242), (233, 250)], fill=HAIR_DK)
    for y in range(236, 255, 3):
        px[238, y] = HAIR_RIM

    # 右侧脸颊 (转过去 30°, 只露出一条)
    poly(d, [(237, 244), (240, 246), (240, 251), (238, 255), (235, 256), (236, 250)], SKIN)
    px[241, 248] = SKIN                                     # 鼻尖
    px[240, 246] = LASH                                     # 睫毛
    px[241, 245] = LASH
    d.line([(235, 255), (237, 255)], fill=SKIN_DK)          # 下颌阴影
    d.line([(236, 240), (236, 248), (237, 257)], fill=HAIR) # 鬓发挡在脸前
    d.line([(237, 239), (239, 243)], fill=HAIR_RIM)

    # 头饰 (她左侧, 在画面左上): 黑色蝴蝶结 + 菊花 + 流苏
    poly(d, [(203, 238), (209, 241), (203, 245)], BLACK)
    poly(d, [(215, 238), (209, 241), (213, 246)], BLACK)
    px[203, 238] = GOLD
    d.line([(208, 243), (207, 251)], fill=CREAM_DK)
    d.line([(210, 243), (210, 249)], fill=CREAM_DK)
    px[207, 252] = GOLD
    px[210, 250] = GOLD
    cx, cy = 211, 235
    d.ellipse([cx - 3, cy - 3, cx + 4, cy + 4], fill=FLOWER)
    for k in range(8):
        a = TAU * k / 8 + 0.2
        px[round(cx + 0.5 + math.cos(a) * 4.6), round(cy + 0.5 + math.sin(a) * 4.6)] = FLOWER
        px[round(cx + 0.5 + math.cos(a) * 2.4), round(cy + 0.5 + math.sin(a) * 2.4)] = FLOWER_HI
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        px[cx + dx, cy + dy] = FLOWER_C


def frame(f):
    """背景层 (512x320): 天空、海、沙滩、影子。人物在 chars_hd.py。"""
    img = Image.new("RGB", (W, H))
    px = img.load()
    draw_background(px, f)
    draw_shadows(ImageDraw.Draw(img))
    return img


def upscale(img):
    return img.resize((W * SCALE, H * SCALE), Image.NEAREST)


def frame_full(f, style):
    import chars_hd
    out = upscale(frame(f))
    ch = chars_hd.draw(f, style).resize((W * SCALE, H * SCALE), Image.NEAREST)
    out.paste(ch, (0, 0), ch)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    styles = sys.argv[2:] or ["B", "C"]
    if mode == "preview":
        for st in styles:
            im = frame_full(0, st)
            im.save(HERE / f"preview_{st}.png")
            im.crop((700, 1110, 1500, 1590)).save(HERE / f"preview_{st}_chars.png")   # 1:1 屏幕像素
        print("ok")
    else:
        for st in styles:
            frames = [frame_full(f, st) for f in range(N)]
            colors = sorted({col for im in frames for _, col in im.getcolors(1 << 20)})
            assert len(colors) <= 256, f"{len(colors)} 色, 超过 GIF 上限"
            pal = Image.new("P", (1, 1))
            pal.putpalette([v for col in colors for v in col] + [0] * (768 - 3 * len(colors)))
            q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
            out = HERE / f"beach_{st}.gif"
            q[0].save(out, save_all=True, append_images=q[1:], duration=FRAME_MS, loop=0, optimize=False, disposal=1)
            print("ok", st, len(colors), "colors,", out.stat().st_size // 1024, "KB")
