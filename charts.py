"""気象庁の天気図を名前で取ってきて、画像にする。
図の名前と取り方の対応は CATALOG。新しい図を足すときはここに1行足す。
"""
import io
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import overlay

WXCHART = "https://www.data.jma.go.jp/yoho/data/wxchart/quick/"
WXLIST = "https://www.jma.go.jp/bosai/weather_map/data/list.json"
NWPMAP = "https://www.jma.go.jp/bosai/numericmap/data/nwpmap/"
DPI = 130

# 名前: (取り方, 気象庁のファイル名, 見出し)
CATALOG = {
    "ASAS": ("asas", 0, "地上天気図 ASAS 最新"),
    "ASAS_12h_ago": ("asas", 12, "地上天気図 ASAS 12時間前"),
    "ASAS_24h_ago": ("asas", 24, "地上天気図 ASAS 24時間前"),
    "ASAS_obs": ("asas_obs", "aupq35", "地上天気図 ASAS"),  # 高層の実況と同じ時刻のASAS
    "FSAS24": ("fsas", 24, "地上 24時間予想 FSAS24"),
    "FSAS48": ("fsas", 48, "地上 48時間予想 FSAS48"),
    "AUPA20": ("nwp", "aupa20", "AUPA20 200hPa 高度・気温・風・圏界面"),
    "AUPQ35": ("nwp", "aupq35", "AUPQ35 300hPa(上)・500hPa(下)"),
    "AUPQ78": ("nwp", "aupq78", "AUPQ78 700hPa(上)・850hPa(下)"),
    "AXFE578": ("nwp", "axfe578", "AXFE578 500hPa高度・渦度／850hPa気温・700hPa上昇流"),
    "FXFE502": ("nwp", "fxfe502", "FXFE502 500hPa高度・渦度／地上気圧・降水量 12・24h"),
    "FXFE504": ("nwp", "fxfe504", "FXFE504 500hPa高度・渦度／地上気圧・降水量 36・48h"),
    "FXFE507": ("nwp", "fxfe507", "FXFE507 500hPa高度・渦度／地上気圧・降水量 72h"),
    "FXFE5782": ("nwp", "fxfe5782", "FXFE5782 500hPa気温・700hPa湿数／850hPa気温・風・700hPa鉛直流 12・24h"),
    "FXFE5784": ("nwp", "fxfe5784", "FXFE5784 500hPa気温・700hPa湿数／850hPa気温・風・700hPa鉛直流 36・48h"),
    "FXFE577": ("nwp", "fxfe577", "FXFE577 500hPa気温・700hPa湿数／850hPa気温・風・700hPa鉛直流 72h"),
    "FUPA302": ("nwp", "fupa302", "FUPA302 300hPa高度・等風速線・気温 24時間予想"),
    "FXJP854": ("nwp", "fxjp854", "FXJP854 850hPa相当温位・風 12〜48h"),
}

ANALYSIS = {"aupa20", "aupq35", "aupq78", "axfe578"}  # 実況図(時刻=観測時刻)。それ以外の nwp は予想図(時刻=初期値)


@dataclass
class Chart:
    name: str
    title: str
    when: str          # 画像に書く時刻の説明
    image: "Image.Image"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Last-Modified")


def pdf_to_image(data):
    import pymupdf  # 更新チェックだけのときは入れずに済むよう、ここで読む
    from PIL import Image
    pix = pymupdf.open(stream=data, filetype="pdf")[0].get_pixmap(dpi=DPI)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def tlabel(t):
    """時刻の書き方: 世界標準時が主、日本時間は括弧。t は UTC。"""
    j = t + timedelta(hours=9)
    return f"{t:%d}日{t:%H}UTC ({j.month}/{j.day} {j.hour}時JST)"


PANEL_DPI = 160


def panel_rects(page):
    """数値予報図のページから、各パネルの枠を 上の行→下の行、左→右 の順に返す(番号 1〜)。"""
    rects = set()
    for g in page.get_drawings():
        for it in g["items"]:
            if it[0] == "re" and it[1].width > 150 and it[1].height > 150:
                rects.add(tuple(round(v, 1) for v in it[1]))
    return sorted(rects, key=lambda r: (round(r[1]), r[0]))


def valid_time(name):
    # list.json のファイル名の2つ目の14桁が対象時刻(UTC)
    return datetime.strptime(re.findall(r"_(\d{14})_MET", name)[0], "%Y%m%d%H%M%S")


def nwp_updated(names):
    """数値予報・高層の図ごとに、気象庁サーバーでの最新の更新時刻(UTC, ISO文字列)を返す。中身は取らない。"""
    out = {}
    for name in names:
        kind, arg, _ = CATALOG[name]
        if kind != "nwp":
            continue
        mods = []
        for hh in ("00", "12"):
            req = urllib.request.Request(f"{NWPMAP}{arg}_{hh}.pdf", method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                mods.append(parsedate_to_datetime(r.headers["Last-Modified"]))
        out[name] = max(mods).astimezone(timezone.utc).isoformat()
    return out


class Fetcher:
    """1回の実行の中で同じ図を2度取りに行かないようにまとめて持つ。"""

    def __init__(self):
        self._list = None
        self._nwp = {}

    def wxlist(self):
        if self._list is None:
            self._list = json.loads(get(WXLIST)[0])["asia_monochrome"]
        return self._list

    def asas(self, back):
        t = valid_time(self.wxlist()["now"][-1]) - timedelta(hours=back)
        data, _ = get(f"{WXCHART}{t:%Y%m}/ASAS_MONO_{t:%Y%m%d%H%M}.pdf")
        return pdf_to_image(data), tlabel(t)

    def asas_obs(self, ref):
        t = self.nwp_pdf(ref)[1]
        data, _ = get(f"{WXCHART}{t:%Y%m}/ASAS_MONO_{t:%Y%m%d%H%M}.pdf")
        return pdf_to_image(data), tlabel(t)

    def fsas(self, ft):
        init = valid_time(self.wxlist()[f"ft{ft}"][-1])
        data, _ = get(f"{WXCHART}FSAS{ft}_MONO_ASIA.pdf")
        return pdf_to_image(data), f"{tlabel(init + timedelta(hours=ft))} 初期値{init:%d}日{init:%H}UTC"

    def nwp_pdf(self, name, prev=False):
        """00UTC版と12UTC版のうち、更新が新しい方の (PDFの中身, 図の時刻UTC)。prev=True なら古い方(1つ前の初期値)。"""
        if name not in self._nwp:
            got = []
            for hh in ("00", "12"):
                data, mod = get(f"{NWPMAP}{name}_{hh}.pdf")
                mod = parsedate_to_datetime(mod).astimezone(timezone.utc).replace(tzinfo=None)
                t = mod.replace(hour=int(hh), minute=0, second=0, microsecond=0)
                if t > mod:
                    t -= timedelta(days=1)
                got.append((t, data))
            got.sort()
            self._nwp[name] = {False: (got[1][1], got[1][0]), True: (got[0][1], got[0][0])}
        return self._nwp[name][prev]

    def nwp(self, name):
        data, t = self.nwp_pdf(name)
        when = tlabel(t) if name in ANALYSIS else f"初期値 {tlabel(t)}"
        return pdf_to_image(data), when

    def panel(self, spec, ft, prev=False):
        """表の1マス分の Chart を返す。ft = 予想時間(0 は実況)。
        spec = "FXFE502.1" のように 図の名前.パネル番号 ならそのパネルだけ切り出す。"ASAS" のように番号なしなら図全体。"""
        if "." not in spec:
            c = self.chart(spec)
            return Chart(spec, f"{'実況' if ft == 0 else f'T={ft}'}  {spec}", c.when, c.image)
        import pymupdf
        from PIL import Image
        name, idx = spec.split(".")
        data, init = self.nwp_pdf(CATALOG[name][1], prev)
        page = pymupdf.open(stream=data, filetype="pdf")[0]
        rects = panel_rects(page)
        x0, y0, x1, y1 = rects[int(idx) - 1]
        # 枠の下にある「T=12 VALID ...」の行も入れる
        clip = pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, min(y1 + 22, page.rect.y1))
        pix = page.get_pixmap(dpi=PANEL_DPI, clip=clip)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        if len(rects) == 1 or name == "FXJP854":
            pos = ""
        elif len(rects) == 4:
            pos = "上段" if int(idx) <= 2 else "下段"
        else:
            pos = "上段" if int(idx) == 1 else "下段"
        head = "実況" if ft == 0 else f"T={ft}"
        if prev:
            pos = (pos + " 1つ前の初期値").strip()
        when = tlabel(init) if ft == 0 else f"{tlabel(init + timedelta(hours=ft))} 初期値{init:%d}日{init:%H}UTC"
        return Chart(spec, f"{head}  {name} {pos}".rstrip(), when, overlay.apply(spec, image))

    def chart(self, name):
        kind, arg, title = CATALOG[name]
        image, when = getattr(self, kind)(arg)
        return Chart(name, title, when, overlay.apply(name, image))
