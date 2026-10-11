"""layout.yml どおりに天気図を並べた画像を作り、メールと LINE で送る。
使い方:
  python -X utf8 run.py --dry-run     画像とページを作るだけ(送らない)
  python -X utf8 run.py --only mail   メールだけ送る
  python -X utf8 run.py --only line   LINE だけ送る(画像が公開URLにある前提)
  python -X utf8 run.py               両方送る
  python -X utf8 run.py --send-only   作り直さず、site/latest.json の画像を送る(Actions で公開後に使う)
  python -X utf8 run.py --check       気象庁の図が前回の配信から更新されたか調べる(changed=true/false)
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import urllib.request

import yaml

from charts import CATALOG, Fetcher, nwp_updated

_here = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(_here, "site")
JST = timezone(timedelta(hours=9))
PAGE_URL = "https://naokishobosai0214-dot.github.io/tenkizu-haishin/"


def load_layout():
    return yaml.safe_load(open(os.path.join(_here, "layout.yml"), encoding="utf-8"))


def layout_names(layout):
    return [n for p in layout["pages"] for n in p["charts"]]


def check():
    """前回配信(公開中の state.json)から、気象庁の図が全部更新されたら changed=true。
    気象庁は 03:36・15:36 UTC(日本時間 12:36・0:36)ごろに高層・数値予報図をまとめて更新する。
    待つ時間帯の最後(UTC 5時台・17時台の50分以降)は、一部だけの更新でも送る。"""
    cur = nwp_updated(layout_names(load_layout()))
    try:
        with urllib.request.urlopen(PAGE_URL + "state.json?t=" + str(int(datetime.now().timestamp())), timeout=30) as r:
            old = json.loads(r.read())["nwp"]
    except Exception:
        old = {}
    fresh = [n for n in cur if cur[n] != old.get(n)]
    utc = datetime.now(timezone.utc)
    last_chance = utc.hour in (5, 17) and utc.minute >= 50
    changed = bool(cur) and (len(fresh) == len(cur) or (bool(fresh) and last_chance))
    if os.environ.get("FORCE") == "true":
        changed = True
    print(f"更新された図 {len(fresh)}/{len(cur)} → changed={changed}")
    if "GITHUB_OUTPUT" in os.environ:
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"changed={'true' if changed else 'false'}\n")


def build():
    from compose import compose  # PIL が要るので、作るときだけ読む
    layout = load_layout()
    os.makedirs(SITE, exist_ok=True)
    nwp = nwp_updated(layout_names(layout))  # 取る前に調べる(取得中に更新されても次回また送れるように)
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
        singles = []  # 1枚ずつ大きく見る用(元の解像度のまま)
        for c in charts:
            f = f"{c.name}_{stamp}.jpg"
            c.image.save(os.path.join(SITE, f), quality=90, optimize=True)
            singles.append({"name": c.name, "title": c.title, "when": c.when, "file": f})
        pages.append({"title": p["title"], "full": full, "preview": prev, "charts": singles})
        print(f"  {p['title']}: {len(charts)}枚 → {full}")
    write_index(pages, made_at)
    open(os.path.join(SITE, "state.json"), "w", encoding="utf-8").write(json.dumps({"nwp": nwp, "made_at": made_at}))
    return pages, now


def write_index(pages, made_at):
    toc = " ".join(f'<a href="#p{i}">{p["title"]}</a>' for i, p in enumerate(pages, 1))
    figs = ""
    for i, p in enumerate(pages, 1):
        figs += f'<h2 id="p{i}">{p["title"]}</h2><a href="{p["full"]}"><img src="{p["full"]}" alt="{p["title"]}"></a>'
        for c in p["charts"]:
            figs += (f'<h3 id="{c["name"]}">{c["title"]} <small>{c["when"]}</small></h3>'
                     f'<a href="{c["file"]}"><img src="{c["file"]}" alt="{c["title"]}" loading="lazy"></a>')
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>天気図配信</title><style>body{{margin:0;padding:16px;font-family:sans-serif;background:#fff;color:#111}}
img{{width:100%;height:auto;border:1px solid #ccc}}h2{{font-size:18px;margin:32px 0 8px;padding:6px 8px;background:#10305a;color:#fff}}
h3{{font-size:15px;margin:20px 0 6px}}h3 small{{font-weight:normal;color:#555}}nav a{{margin-right:12px}}</style></head>
<body><h1 style="font-size:20px">天気図配信 <small>{made_at}</small></h1>
<nav>{toc}</nav><p style="font-size:13px;color:#555">まとめ画像のあとに1枚ずつの図があります。図をタップすると原寸で開きます(拡大できます)。</p>{figs}
<p style="color:#666;font-size:12px">出典：気象庁ホームページ</p></body></html>"""
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(SITE, "latest.json"), "w", encoding="utf-8").write(json.dumps(pages, ensure_ascii=False))
    open(os.path.join(SITE, ".nojekyll"), "w").close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["mail", "line"])
    ap.add_argument("--send-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
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
