"""LINE Messaging API で自分に天気図を送る(プッシュ)。
画像は公開URL(GitHub Pages)から読まれるので、ページを公開したあとに呼ぶ。
1回の送信で吹き出しは最大5つ: テキスト1つ + 画像4枚まで。
環境変数: LINE_CHANNEL_TOKEN, LINE_USER_ID, PAGE_URL(末尾 / 付きの公開URL)
"""
import json
import os
import urllib.request


def send(subject, pages):
    base = os.environ["PAGE_URL"].rstrip("/") + "/"
    text = subject + "\n" + "\n".join(f"・{p['title']}" for p in pages) + f"\n\n{base}\n出典：気象庁"
    messages = [{"type": "text", "text": text}]
    for p in pages[:4]:
        messages.append({"type": "image", "originalContentUrl": base + p["full"], "previewImageUrl": base + p["preview"]})
    body = json.dumps({"to": os.environ["LINE_USER_ID"], "messages": messages}).encode()
    req = urllib.request.Request("https://api.line.me/v2/bot/message/push", data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["LINE_CHANNEL_TOKEN"],
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"  LINE送信: {r.status}")
