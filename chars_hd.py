"""人物图层 (高精度): Claude 娘 + Clawd, 侧后方 30° 视角。

坐标仍用背景画布单位 (512x320), 栅格化到 2.5 倍 (1280x800), 再放大 2 倍贴到 2560x1600。
轮廓全部是 Catmull-Rom 平滑样条; 朝月亮 (右上) 的边缘自动勾月光亮边。

style:
  "B"  上色版
  "C"  逆光剪影版
"""
import math

import numpy as np
from PIL import Image, ImageDraw

K = 2.5
HW, HH = 1280, 800
TAU = math.tau
N = 24


def c(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.uint8)


STYLES = {
    "B": dict(
        hair=c("#A9533A"), hair_dk=c("#7A3829"), hair_dkk=c("#55271F"), hair_hi=c("#CF7A4C"), hair_rim=c("#F2AE74"),
        skin=c("#D9BBAD"), skin_dk=c("#A88A82"), skin_rim=c("#F3DCCF"), lash=c("#2A1A1C"),
        cream=c("#BDB5A5"), cream_dk=c("#8A8275"), cream_rim=c("#E6DFCF"),
        orange=c("#B4613A"), black=c("#1A161F"), black_rim=c("#5A5060"), gold=c("#B08A42"),
        flower=c("#D2743E"), flower_hi=c("#EE9C5E"), flower_c=c("#7C3420"),
        cl_back=c("#A6563F"), cl_dk=c("#86432F"), cl_side=c("#C96D50"), cl_rim=c("#EC9A74"),
        ao=c("#3A3340"),
    ),
    "C": dict(
        hair=c("#3A1D1B"), hair_dk=c("#2A1416"), hair_dkk=c("#211014"), hair_hi=c("#55291F"), hair_rim=c("#E69B63"),
        skin=c("#1A1420"), skin_dk=c("#1A1420"), skin_rim=c("#E3CCBE"), lash=c("#1A1420"),
        cream=c("#1B1724"), cream_dk=c("#16121E"), cream_rim=c("#CFC7B4"),
        orange=c("#2C1A1E"), black=c("#100D15"), black_rim=c("#8E8496"), gold=c("#6E5630"),
        flower=c("#9A4A28"), flower_hi=c("#C46A38"), flower_c=c("#4A2016"),
        cl_back=c("#3A201C"), cl_dk=c("#2E1917"), cl_side=c("#5A2E24"), cl_rim=c("#E8946A"),
        ao=c("#0C0A10"),
    ),
}


def catmull(pts, closed=True, n=12):
    out = []
    L = len(pts)
    idx = range(L) if closed else range(L - 1)
    for i in idx:
        if closed:
            p0, p1, p2, p3 = pts[(i - 1) % L], pts[i], pts[(i + 1) % L], pts[(i + 2) % L]
        else:
            p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, L - 1)]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                       + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
                for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def ribbon(center, w0, w1):
    """沿中心线生成一条由宽 w0 渐细到 w1 的带状多边形 (发束)。"""
    pts = catmull(center, closed=False, n=8)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = (w0 + (w1 - w0) * i / (len(pts) - 1)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def hi(pts):
    return [(x * K, y * K) for x, y in pts]


class Layer:
    def __init__(self):
        self.rgb = np.zeros((HH, HW, 3), np.uint8)
        self.a = np.zeros((HH, HW), bool)

    @staticmethod
    def shape(pts, smooth=True):
        m = Image.new("L", (HW, HH), 0)
        ImageDraw.Draw(m).polygon(hi(catmull(pts) if smooth else pts), fill=255)
        return np.array(m) > 0

    @staticmethod
    def poly(pts):
        m = Image.new("L", (HW, HH), 0)
        ImageDraw.Draw(m).polygon(hi(pts), fill=255)
        return np.array(m) > 0

    @staticmethod
    def ellipse(cx, cy, rx, ry):
        m = Image.new("L", (HW, HH), 0)
        ImageDraw.Draw(m).ellipse([(cx - rx) * K, (cy - ry) * K, (cx + rx) * K, (cy + ry) * K], fill=255)
        return np.array(m) > 0

    @staticmethod
    def stroke(pts, width):
        m = Image.new("L", (HW, HH), 0)
        ImageDraw.Draw(m).line(hi(catmull(pts, closed=False)), fill=255, width=max(1, round(width * K)), joint="curve")
        return np.array(m) > 0

    @staticmethod
    def rect(x0, y0, x1, y1):
        m = np.zeros((HH, HW), bool)
        m[round(y0 * K):round(y1 * K), round(x0 * K):round(x1 * K)] = True
        return m

    def paint(self, m, col, clip=None):
        if clip is not None:
            m = m & clip
        self.rgb[m] = col
        self.a |= m

    def rim(self, m, col, r=2, clip=None):
        """m 里朝右上 (月亮方向) 的边缘。"""
        sh = np.zeros_like(m)
        sh[r:, :-r] = m[:-r, r:]
        self.paint(m & ~sh, col, clip)

    def edge(self, m, col, r=2):
        """m 里背光 (左下) 一侧的边缘: 叠在别的部件上时把两者分开。"""
        sh = np.zeros_like(m)
        sh[:-r, r:] = m[r:, :-r]
        self.paint(m & ~sh, col)

    def part(self, m, col, rim=None, r=2, ao=None):
        self.paint(m, col)
        if ao is not None:
            self.edge(m, ao, 2)
        if rim is not None:
            self.rim(m, rim, r)
        return m

    def image(self):
        out = np.zeros((HH, HW, 4), np.uint8)
        out[..., :3] = self.rgb
        out[..., 3] = self.a * 255
        return Image.fromarray(out, "RGBA")


def draw(f, style="B"):
    S = STYLES[style]
    L = Layer()
    sway = math.sin(TAU * f / N)

    def sw(y):
        return sway * max(0.0, (y - 262) / 50) * 2.0

    # ---------- Clawd: 像素方块就是它本来的样子, 按 2 单位一格画 ----------
    ox, oy = 150, 279 + (1 if 10 <= f < 13 else 0)
    lift = 1 if 16 <= f < 20 else 0

    def blk(x0, y0, x1, y1):
        return L.rect(ox + x0 * 2, oy + y0 * 2, ox + (x1 + 1) * 2, oy + (y1 + 1) * 2)

    body = blk(3, 0, 14, 7)
    L.paint(body, S["cl_back"])
    L.paint(blk(3, 6, 14, 7), S["cl_dk"])
    L.paint(blk(1, 4, 2, 5), S["cl_dk"])
    side = blk(15, 0, 15, 7) | blk(16, 4 - lift, 17, 5 - lift)
    L.paint(side, S["cl_side"])
    for lx in (4, 6, 11, 13):
        L.paint(blk(lx, 8, lx, 8), S["cl_dk"] if lx < 13 else S["cl_side"])
    L.rim(body | side | blk(1, 4, 2, 5), S["cl_rim"], r=2)

    # ---------- Claude 娘 ----------
    # 比例: 头宽 26, 肩宽 34 (溜肩), 手臂细
    ao = S["ao"]

    # 参考 Claude 娘设定图背面: 背后一条较窄的直发, 两侧几缕大波浪卷发从肩后垂下;
    # 短披肩到上臂, 蓬袖收窄到荷叶袖口; 束腰很细 (约 0.7 头宽), 裙摆大幅散开。
    # 身体右转 30°: 头发中线略偏左, 右侧露得多一点。

    # 裙子: 从细腰散开铺在沙上; 同一形状叠三次露出橙/黑两道裙层
    skirt = [(201, 303), (205, 296), (211, 291), (215.6, 287.4), (226, 286.8), (236.6, 287.4), (242, 291),
             (250, 295), (255.5, 299.5), (254, 305), (242, 308.4), (226, 309.4), (209, 308.4)]
    L.part(L.shape(skirt), S["orange"])
    L.part(L.shape([(x, y - 1.2) for x, y in skirt]), S["black"], S["black_rim"])
    L.part(L.shape([(x, y - 2.6) for x, y in skirt]), S["cream_dk"], S["cream_rim"], ao=ao)
    if style == "B":
        L.paint(L.shape([(238, 287.6), (243, 291), (250, 294.6), (254.4, 298.6), (249, 299.2), (241.6, 293.6)]), S["cream"])

    # 腿朝前伸向海边, 从背后看被身体和裙子挡住, 不画

    # 手臂: 上臂蓬袖, 前臂收紧, 撑到身后的沙上
    larm = [(212, 264.4), (209, 267.4), (207.8, 272.4), (206.4, 278.6), (204.8, 284.4), (203.8, 288.6), (206, 289),
            (207.2, 284.8), (209, 279), (210.8, 274), (213, 270)]
    L.part(L.shape(larm), S["cream_dk"], S["cream_rim"], ao=ao)
    L.part(L.shape([(202.8, 287.4), (205.4, 286.6), (207.6, 288), (207.2, 290.6), (204.2, 291.2), (202.6, 289.8)]),
           S["black"], S["black_rim"], r=1)
    L.part(L.shape([(202.8, 290.6), (206.6, 290.4), (207.4, 292.6), (205.2, 294.2), (202.4, 293.4)]), S["skin_dk"], S["skin_rim"], r=1)

    rarm = [(239.6, 264.4), (242.8, 267.4), (244.2, 272.4), (245.8, 278.6), (247.4, 284.4), (248.4, 288.6), (246.2, 289),
            (245, 284.8), (243.2, 279), (241.4, 274), (239, 270)]
    L.part(L.shape(rarm), S["cream"], S["cream_rim"], ao=ao)
    L.part(L.shape([(244.8, 287.4), (247.6, 286.6), (249.6, 288), (249.2, 290.6), (246, 291.2), (244.6, 289.8)]),
           S["black"], S["black_rim"], r=1)
    L.part(L.shape([(245.6, 290.6), (249.4, 290.4), (251.2, 292), (250.2, 293.8), (246, 293.8)]), S["skin"], S["skin_rim"], r=1)

    # 衬衫后背 + 细束腰
    blouse = [(212.6, 267), (226, 266.6), (239.4, 267), (237.6, 271.4), (235.8, 275), (226, 275.4), (216.2, 275), (214.4, 271.4)]
    L.part(L.shape(blouse), S["cream_dk"], S["cream_rim"], ao=ao)
    if style == "B":
        L.paint(L.shape([(233, 266.8), (239.4, 267), (237.6, 271.4), (235.8, 275), (233.4, 275.2), (234, 270.6)]), S["cream"])
    corset = [(216.4, 274.2), (226, 273.8), (235.6, 274.2), (234.6, 279.4), (236.6, 287.4), (226, 288), (215.4, 287.4), (217.4, 279.4)]
    L.part(L.shape(corset), S["black"], S["black_rim"])
    if style == "B":
        for y in (277.5, 280.5, 283.5):
            L.paint(L.ellipse(233.4, y, 0.5, 0.5), S["gold"])

    # 短披肩: 窄溜肩, 下摆到上臂, 微微外展
    cape = [(219.6, 256.8), (215, 259), (212, 262), (210.4, 265.4), (209.6, 268.8), (214, 269.8), (220, 270.2),
            (226, 270.3), (232, 270.2), (238, 269.8), (242.4, 268.8), (241.6, 265.4), (240, 262), (237, 259), (232.4, 256.8)]
    capem = L.part(L.shape(cape), S["cream_dk"])
    if style == "B":
        L.paint(L.shape([(232.4, 256.8), (237, 259), (240, 262), (241.6, 265.4), (242.4, 268.8), (236.6, 269.9),
                         (236.4, 263.6), (234.6, 259)]), S["cream"], clip=capem)
        for k in range(8):   # 披肩上的橙色菊纹
            a = TAU * k / 8
            L.paint(L.stroke([(238.4, 265.2), (238.4 + 1.3 * math.cos(a), 265.2 + 1.3 * math.sin(a))], 0.4), S["orange"])
    L.edge(capem, ao, 2)
    L.rim(capem, S["cream_rim"], r=2)

    # ---- 头发 ----
    def swp(pts):
        return [(x + sw(y), y) for x, y in pts]

    headm = L.ellipse(225, 243.6, 12.4, 13)

    # 两侧的大波浪卷发 (先画, 被后背的直发压住一部分): 从头部长出, S 形垂到裙子上打卷
    locks = [
        ([(214.6, 245), (212.8, 254), (211.6, 263), (209.8, 271), (210.2, 279), (207.8, 287), (205.4, 294), (206, 299.6), (208.8, 300.6)], 4.8, 1.6, 0.0),
        ([(217, 248), (215.6, 257), (214.8, 266), (213.4, 274), (213.6, 282), (211.8, 290), (210.6, 297), (212.4, 301)], 3.4, 1.2, 1.7),
        ([(235.4, 245), (237.4, 254), (238.8, 263), (241, 271), (240.8, 279), (243.4, 287), (246, 294), (245.4, 299.6), (242.6, 300.6)], 4.8, 1.6, 0.6),
        ([(233.2, 248), (234.6, 257), (235.6, 266), (237.2, 274), (237.2, 282), (239.2, 290), (240.6, 297), (238.8, 301)], 3.4, 1.2, 2.3),
    ]
    for center, w0, w1, ph in locks:
        wav = [(x + 1.1 * math.sin(y * 0.3 + ph) + sw(y) * 1.2, y) for x, y in center]
        m = L.poly(ribbon(wav, w0, w1)) & ~headm
        L.paint(m, S["hair"])
        L.paint(L.stroke([(x - 0.6, y) for x, y in wav[1:-2]], 0.35), S["hair_dk"], clip=m)
        L.paint(L.stroke([(x + 0.8, y) for x, y in wav[1:-3]], 0.3), S["hair_hi"], clip=m)
        L.edge(m, S["hair_dkk"], 1)
        L.rim(m, S["hair_rim"], r=2)

    # 背后正中一条直发: 约 0.65 头宽, 落到裙子上才散开, 发梢参差
    back = [(217.2, 250), (217.6, 260), (217.8, 270), (218, 280), (217.4, 289), (215, 297), (211.6, 303), (209.4, 307.4),
            (212.4, 310.2), (215.6, 309.6), (219.6, 311.4), (223.4, 310.4), (227.6, 311.6), (231.4, 310.2),
            (235.6, 310.8), (238.6, 308.6), (240.2, 306.2), (237.6, 302),
            (234.8, 296), (233.2, 288), (232.6, 279), (232.6, 269), (232.6, 259), (233, 250)]
    backm = L.shape(swp(back))
    hairm = backm | headm
    L.paint(hairm, S["hair"])
    L.edge(hairm, S["hair_dkk"], 2)
    for x0, key, spread in [(219.6, "hair_dkk", -0.6), (222, "hair_dk", -0.3), (224.4, "hair_dkk", 0.0),
                            (226.8, "hair_dk", 0.25), (229.2, "hair_dkk", 0.5), (231.2, "hair_hi", 0.75), (221, "hair_hi", -0.45)]:
        pts = [(x0 + spread * 14 * ((y - 250) / 60) ** 2 + 0.6 * math.sin(y * 0.21 + x0) + sw(y), y) for y in range(250, 314, 4)]
        L.paint(L.stroke(pts, 0.4), S[key], clip=backm)

    # 后脑勺: 光泽 + 编发
    if style == "B":
        L.paint(L.ellipse(225, 239, 9.8, 5.6) & ~L.ellipse(225, 240.8, 9.4, 5.4), S["hair_hi"], clip=headm)
    for k in range(9):
        x = 215.8 + k * 2.3
        y = 238.4 + 0.9 * math.sin(k * 0.4)
        L.paint(L.ellipse(x, y, 1.25, 0.8), S["hair_dk"], clip=headm)
        L.paint(L.ellipse(x + 0.3, y - 0.3, 0.7, 0.35), S["hair_hi"], clip=headm)
    for pts in ([(225.2, 241), (224.4, 248), (225.2, 256)], [(219.5, 242.5), (217.6, 249.5), (218.4, 256.5)],
                [(230.8, 242.5), (232, 249.5)]):
        L.paint(L.stroke(pts, 0.42), S["hair_dk"], clip=headm)

    # 右脸颊: 只露出一道圆弧
    cheek = [(235.4, 248.4), (236.7, 250.4), (237.1, 252.6), (236.4, 254.8), (235, 256), (234.4, 252.4)]
    L.part(L.shape(cheek), S["skin"], S["skin_rim"], r=1)
    L.rim(hairm & ~L.shape(cheek), S["hair_rim"], r=2)

    # 头饰 (她的左侧 = 画面左上): 黑色蝴蝶结 + 菊花 + 金色流苏
    tails = L.stroke([(209, 242.4), (208, 246.8), (206.8, 251)], 1.0) | L.stroke([(210.8, 242.4), (211, 246.2), (210.6, 250)], 1.0)
    L.part(tails, S["black"], S["black_rim"], r=1)
    L.paint(L.ellipse(206.8, 251.6, 0.7, 1.0) | L.ellipse(210.6, 250.6, 0.7, 1.0), S["gold"])
    loop_l = [(210.2, 240.6), (207.6, 237.4), (204.6, 236.8), (203.4, 239), (204.6, 242), (207.4, 242.8)]
    loop_m = L.part(L.shape(loop_l), S["black"], S["black_rim"], r=1)
    L.paint(L.stroke([(209.4, 240.6), (206.4, 239.2)], 0.35), S["black_rim"], clip=loop_m)   # 环内折痕
    L.part(L.ellipse(210.4, 241.2, 1.2, 1.2), S["black"])
    cx, cy = 211.6, 236.2
    outer = np.zeros((HH, HW), bool)
    inner = np.zeros((HH, HW), bool)
    for k in range(16):   # 尖花瓣: 菱形, 外圈 16 瓣 + 内圈 10 瓣
        a = TAU * k / 16
        ca, sa = math.cos(a), math.sin(a)
        outer |= L.shape([(cx + 1.2 * ca, cy + 1.2 * sa), (cx + 2.8 * ca - 0.75 * sa, cy + 2.8 * sa + 0.75 * ca),
                          (cx + 4.6 * ca, cy + 4.6 * sa), (cx + 2.8 * ca + 0.75 * sa, cy + 2.8 * sa - 0.75 * ca)], smooth=False)
    for k in range(10):
        a = TAU * k / 10 + 0.3
        ca, sa = math.cos(a), math.sin(a)
        inner |= L.shape([(cx + 0.8 * ca, cy + 0.8 * sa), (cx + 2 * ca - 0.6 * sa, cy + 2 * sa + 0.6 * ca),
                          (cx + 3.1 * ca, cy + 3.1 * sa), (cx + 2 * ca + 0.6 * sa, cy + 2 * sa - 0.6 * ca)], smooth=False)
    L.part(outer, S["flower"])
    L.paint(inner, S["flower_hi"])
    L.paint(L.ellipse(cx, cy, 1.2, 1.2), S["flower_c"])

    return L.image()
