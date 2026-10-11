"""layout.yml どおりに天気図を並べた画像を作り、メールと LINE で送る。
使い方:
  python -X utf8 run.py --dry-run     画像とページを作るだけ(送らない)
  python -X utf8 run.py --only mail   メールだけ送る
  python -X utf8 run.py --only line   LINE だけ送る(画像が公開URLにある前提)
  python -X utf8 run.py               両方送る
  python -X utf8 run.py --send-only   作り直さず、site/latest.json の画像を送る(Actions で公開後に使う)
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import yaml

from charts import CATALOG, Fetcher
from compose import compose

_here = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(_here, "site")
JST = timezone(timedelta(hours=9))


def build():
    layout = yaml.safe_load(open(os.path.join(_here, "layout.yml"), encoding="utf-8"))
    os.makedirs(SITE, exist_ok=True)
    now = datetime.now(JST)
    stamp = now.strftime("%Y%m%d%H%M")
    made_at = f"{now:%Y/%m/%d %H:%M} JST 作成"
    fetcher = Fetcher()
    pages = []
    for i, p in enumerate(layout["pages"], 1):
        charts = []
        for name in p["charts"]:
            if name not in CATALOG:
                raise SystemExit(f"layout.yml の図の名前が違います: {name}")
            try:
                charts.append(fetcher.chart(name))
            except Exception as e:  # 1枚取れなくても他は送る
                print(f"  取得できず {name}: {e}")
        if not charts:
            continue
        img = compose(p["title"], charts, p.get("cols", 2), made_at)
        full = f"p{i}_{stamp}.jpg"
        prev = f"p{i}_{stamp}_s.jpg"
        img.save(os.path.join(SITE, full), quality=85, optimize=True)
        img.thumbnail((1024, 1024))
        img.save(os.path.join(SITE, prev), quality=80, optimize=True)
        pages.append({"title": p["title"], "full": full, "preview": prev})
        print(f"  {p['title']}: {len(charts)}枚 → {full}")
    write_index(pages, made_at)
    return pages, now


def write_index(pages, made_at):
    figs = "\n".join(f'<h2>{p["title"]}</h2><a href="{p["full"]}"><img src="{p["full"]}" alt="{p["title"]}"></a>' for p in pages)
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>天気図配信</title><style>body{{margin:0;padding:16px;font-family:sans-serif;background:#fff;color:#111}}
img{{width:100%;height:auto;border:1px solid #ccc}}h2{{font-size:18px;margin:24px 0 8px}}</style></head>
<body><h1 style="font-size:20px">天気図配信 <small>{made_at}</small></h1>{figs}
<p style="color:#666;font-size:12px">出典：気象庁ホームページ</p></body></html>"""
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(SITE, "latest.json"), "w", encoding="utf-8").write(json.dumps(pages, ensure_ascii=False))
    open(os.path.join(SITE, ".nojekyll"), "w").close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["mail", "line"])
    ap.add_argument("--send-only", action="store_true")
    a = ap.parse_args()
    if a.send_only:
        pages = json.load(open(os.path.join(SITE, "latest.json"), encoding="utf-8"))
        now = datetime.now(JST)
    else:
        pages, now = build()
    if a.dry_run or not pages:
        return
    subject = f"天気図 {now:%m/%d %H:%M}"
    if a.only in (None, "mail"):
        import send_mail
        send_mail.send(subject, pages, SITE)
    if a.only in (None, "line"):
        import send_line
        send_line.send(subject, pages)


if __name__ == "__main__":
    main()
