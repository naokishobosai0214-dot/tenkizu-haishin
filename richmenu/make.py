"""LINE のトーク画面の下に出すボタン(リッチメニュー)を作って登録する。
画像を作る → メニューを作る → 画像を載せる → 全員(自分)の既定にする → 古いメニューを消す。
環境変数: LINE_CHANNEL_TOKEN。使い方: python -X utf8 richmenu/make.py [--image-only]
ボタンを変えたいときは BUTTONS を書き換えて、Actions の richmenu を手動実行する。
"""
import io
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

PAGE = "https://naokishobosai0214-dot.github.io/tenkizu-haishin/"
W, H = 2500, 843  # 小さい方の大きさ(3×2)
# (見出し, 説明, 開くURL)。openExternalBrowser=1 は LINE の中ではなく Safari などで開く
BUTTONS = [
    ("地上天気図", "実況 → 48時間後", PAGE + "#p1"),
    ("実況天気図", "200hPa → 地上", PAGE + "#p2"),
    ("数値予報", "12 → 48時間", PAGE + "#p3"),
    ("PDF", "GoodNotes 用", PAGE + "latest.pdf?openExternalBrowser=1"),
    ("ページ全体", "1枚ずつ原寸", PAGE + "?openExternalBrowser=1"),
    # Google ドライブの「天気図アーカイブ」(nao.kishobosai.0214 のドライブ。Apps Script が毎回保存する)
    ("アーカイブ", "過去の配信", "https://drive.google.com/drive/folders/1D9bLiKvaKTfKRdQrGeFbNVJvDPVXLtNr?openExternalBrowser=1"),
]
_here = os.path.dirname(os.path.abspath(__file__))
FONT_B = os.path.join(_here, "..", "fonts", "BIZUDGothic-Bold.ttf")
FONT_R = os.path.join(_here, "..", "fonts", "BIZUDGothic-Regular.ttf")
NAVY, LIGHT, ACCENT = (16, 42, 84), (232, 238, 247), (208, 0, 0)


def boxes():
    cw, ch = W // 3, H // 2
    return [(c * cw, r * ch, cw if c < 2 else W - 2 * cw, ch) for r in range(2) for c in range(3)]


def make_image():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    for i, ((title, sub, _), (x, y, w, h)) in enumerate(zip(BUTTONS, boxes())):
        top = i < 3
        d.rectangle([x, y, x + w, y + h], fill=NAVY if top else LIGHT)
        d.rectangle([x, y, x + w, y + h], outline="white", width=6)
        fg = "white" if top else NAVY
        d.text((x + w // 2, y + h // 2 - 40), title, font=ImageFont.truetype(FONT_B, 92), fill=fg, anchor="mm")
        d.text((x + w // 2, y + h // 2 + 62), sub, font=ImageFont.truetype(FONT_R, 50),
               fill=(200, 214, 235) if top else (70, 80, 100), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue(), img


def api(method, url, body=None, ctype="application/json"):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + os.environ["LINE_CHANNEL_TOKEN"], "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read()
        return json.loads(txt) if txt else {}


def main():
    png, img = make_image()
    if "--image-only" in sys.argv:
        img.save(os.path.join(_here, "richmenu.png"))
        print("richmenu.png を作りました")
        return
    menu = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": "天気図配信",
        "chatBarText": "天気図メニュー",
        "areas": [{"bounds": {"x": x, "y": y, "width": w, "height": h}, "action": {"type": "uri", "label": t, "uri": u}}
                  for (t, _, u), (x, y, w, h) in zip(BUTTONS, boxes())],
    }
    old = [m["richMenuId"] for m in api("GET", "https://api.line.me/v2/bot/richmenu/list").get("richmenus", [])]
    rid = api("POST", "https://api.line.me/v2/bot/richmenu", menu)["richMenuId"]
    api("POST", f"https://api-data.line.me/v2/bot/richmenu/{rid}/content", png, "image/png")
    api("POST", f"https://api.line.me/v2/bot/user/all/richmenu/{rid}")
    for m in old:
        api("DELETE", f"https://api.line.me/v2/bot/richmenu/{m}")
    print(f"リッチメニューを登録しました(古いもの {len(old)} 件を削除)")


if __name__ == "__main__":
    main()
