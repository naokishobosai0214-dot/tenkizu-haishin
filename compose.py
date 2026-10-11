"""layout.yml の1ページ分の図を、決めた列数で1枚の画像に並べる。"""
import os

from PIL import Image, ImageDraw, ImageFont

_here = os.path.dirname(os.path.abspath(__file__))
FONT_B = os.path.join(_here, "fonts", "BIZUDGothic-Bold.ttf")
FONT_R = os.path.join(_here, "fonts", "BIZUDGothic-Regular.ttf")

W = 2400
PAD, GAP = 20, 16
HEAD, FOOT, CAP = 84, 44, 62     # ページ見出し帯・出典帯・各図の見出し(2行)の高さ
NAVY, GRAY = (16, 42, 84), (232, 236, 242)


def font(size, bold=True):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def compose(title, charts, cols, made_at):
    """charts: charts.Chart のリスト。made_at: 作成時刻の文字列。"""
    W = 2400 if cols <= 3 else 800 * cols  # 4列以上は横に広げて1枚が小さくなりすぎないように
    rows = [charts[i:i + cols] for i in range(0, len(charts), cols)]
    # 1行の図は高さをそろえ、縦長・横長が混ざっても行の横幅いっぱいに並べる
    full = W - PAD * 2
    scaled = []
    for r in rows:
        n = len(r) if len(r) == cols or len(rows) == 1 else cols  # 最後の半端な行は前の行と同じくらいの大きさに
        ratios = [c.image.width / c.image.height for c in r]
        h = (full - GAP * (n - 1)) / (sum(ratios) * n / len(r))
        scaled.append([c.image.resize((round(h * a), round(h)), Image.LANCZOS) for c, a in zip(r, ratios)])
    heights = [CAP + max(im.height for im in r) for r in scaled]
    H = HEAD + sum(heights) + GAP * (len(rows) - 1) + FOOT + PAD
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, HEAD - 12], fill=NAVY)
    d.text((PAD, (HEAD - 12) // 2), title, font=font(40), fill="white", anchor="lm")
    d.text((W - PAD, (HEAD - 12) // 2), made_at, font=font(24, False), fill="white", anchor="rm")

    y = HEAD
    for r, ims, rh in zip(rows, scaled, heights):
        x = PAD
        for c, im in zip(r, ims):
            cw = im.width
            caption(d, x, y, cw, c)
            img.paste(im, (x, y + CAP))
            d.rectangle([x, y, x + cw, y + CAP + im.height], outline=(150, 150, 150), width=2)
            x += cw + GAP
        y += rh + GAP

    d.text((W - PAD, H - FOOT // 2 - 4), "出典：気象庁ホームページ(天気図)", font=font(20, False), fill=(90, 90, 90), anchor="rm")
    return img


ROWHEAD = 52     # 表の各行の上の帯(高さの層と、引用した天気図)
CELL_W = 700     # 表の1マスの幅


def caption(d, x, y, cw, c):
    """図の上の2行の見出し(1行目=名前、2行目=時刻)。"""
    d.rectangle([x, y, x + cw, y + CAP], fill=GRAY)
    size = 22
    while size > 12 and d.textlength(c.title, font=font(size)) > cw - 20:
        size -= 1
    d.text((x + 10, y + 18), c.title, font=font(size), fill=NAVY, anchor="lm")
    d.text((x + 10, y + 45), c.when, font=font(18, False), fill=(40, 40, 40), anchor="lm")


def compose_matrix(title, rows, ncols, made_at):
    """予想時間を横、高さの層を縦に並べた表。
    rows: [(行の見出し, 引用した天気図の説明, [Chart または None, ...]), ...]"""
    W = PAD * 2 + CELL_W * ncols + GAP * (ncols - 1)
    scaled = []
    for _, _, cells in rows:
        scaled.append([c.image.resize((CELL_W, round(c.image.height * CELL_W / c.image.width)), Image.LANCZOS) if c else None
                       for c in cells])
    heights = [ROWHEAD + CAP + max(im.height for im in r if im) for r in scaled]
    H = HEAD + sum(heights) + GAP * len(rows) + FOOT
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, HEAD - 12], fill=NAVY)
    d.text((PAD, (HEAD - 12) // 2), title, font=font(40), fill="white", anchor="lm")
    d.text((W - PAD, (HEAD - 12) // 2), made_at, font=font(24, False), fill="white", anchor="rm")

    y = HEAD
    for (label, source, cells), ims, rh in zip(rows, scaled, heights):
        d.rectangle([PAD, y, W - PAD, y + ROWHEAD - 6], fill=(214, 226, 242))
        d.text((PAD + 12, y + (ROWHEAD - 6) // 2), label, font=font(30), fill=NAVY, anchor="lm")
        lw = d.textlength(label, font=font(30))
        d.text((PAD + 36 + lw, y + (ROWHEAD - 6) // 2), "引用：" + source, font=font(22, False), fill=(40, 40, 40), anchor="lm")
        cy = y + ROWHEAD
        for i, (c, im) in enumerate(zip(cells, ims)):
            if not c:
                continue
            x = PAD + i * (CELL_W + GAP)
            caption(d, x, cy, CELL_W, c)
            img.paste(im, (x, cy + CAP))
            d.rectangle([x, cy, x + CELL_W, cy + CAP + im.height], outline=(150, 150, 150), width=2)
        y += rh + GAP

    d.text((W - PAD, H - FOOT // 2 - 4), "出典：気象庁ホームページ(数値予報天気図)", font=font(20, False), fill=(90, 90, 90), anchor="rm")
    return img
