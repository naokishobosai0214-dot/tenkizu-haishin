"""layout.yml の1ページ分の図を、決めた列数で1枚の画像に並べる。"""
import os

from PIL import Image, ImageDraw, ImageFont

_here = os.path.dirname(os.path.abspath(__file__))
FONT_B = os.path.join(_here, "fonts", "BIZUDGothic-Bold.ttf")
FONT_R = os.path.join(_here, "fonts", "BIZUDGothic-Regular.ttf")

W = 2400
PAD, GAP = 20, 16
HEAD, FOOT, CAP = 84, 44, 44     # ページ見出し帯・出典帯・各図の見出しの高さ
NAVY, GRAY = (16, 42, 84), (232, 236, 242)


def font(size, bold=True):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def compose(title, charts, cols, made_at):
    """charts: charts.Chart のリスト。made_at: 作成時刻の文字列。"""
    cw = (W - PAD * 2 - GAP * (cols - 1)) // cols
    rows = [charts[i:i + cols] for i in range(0, len(charts), cols)]
    scaled = [[c.image.resize((cw, round(c.image.height * cw / c.image.width)), Image.LANCZOS) for c in r] for r in rows]
    heights = [CAP + max(im.height for im in r) for r in scaled]
    H = HEAD + sum(heights) + GAP * (len(rows) - 1) + FOOT + PAD
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, HEAD - 12], fill=NAVY)
    d.text((PAD, (HEAD - 12) // 2), title, font=font(40), fill="white", anchor="lm")
    d.text((W - PAD, (HEAD - 12) // 2), made_at, font=font(24, False), fill="white", anchor="rm")

    y = HEAD
    for r, ims, rh in zip(rows, scaled, heights):
        for i, (c, im) in enumerate(zip(r, ims)):
            x = PAD + i * (cw + GAP)
            d.rectangle([x, y, x + cw, y + CAP], fill=GRAY)
            wf = font(20, False)
            room = cw - 30 - d.textlength(c.when, font=wf)
            size = 22
            while size > 12 and d.textlength(c.title, font=font(size)) > room:  # 長い見出しは文字を小さくして収める
                size -= 1
            d.text((x + 10, y + CAP // 2), c.title, font=font(size), fill=NAVY, anchor="lm")
            d.text((x + cw - 10, y + CAP // 2), c.when, font=wf, fill=(40, 40, 40), anchor="rm")
            img.paste(im, (x, y + CAP))
            d.rectangle([x, y, x + cw, y + CAP + im.height], outline=(150, 150, 150), width=2)
        y += rh + GAP

    d.text((W - PAD, H - FOOT // 2 - 4), "出典：気象庁ホームページ(天気図)", font=font(20, False), fill=(90, 90, 90), anchor="rm")
    return img
