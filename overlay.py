"""天気図への書き込み(将来用)。
図の名前ごとに書き込み関数を登録すると、取得した画像にその書き込みをしてから並べる。
例: HANDLERS["AUPQ35"] = [等温線を青でなぞる関数, 強風軸を描く関数]
今は何も登録していないので、気象庁の図がそのまま並ぶ。
"""
HANDLERS = {}


def apply(name, image):
    for fn in HANDLERS.get(name, []):
        image = fn(image)
    return image
