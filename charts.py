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

import pymupdf
from PIL import Image

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
    "FXJP854": ("nwp", "fxjp854", "FXJP854 850hPa相当温位・風 12〜48h"),
}

ANALYSIS = {"aupa20", "aupq35", "aupq78", "axfe578"}  # 実況図(時刻=観測時刻)。それ以外の nwp は予想図(時刻=初期値)


@dataclass
class Chart:
    name: str
    title: str
    when: str          # 画像に書く時刻の説明
    image: Image.Image


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Last-Modified")


def pdf_to_image(data):
    pix = pymupdf.open(stream=data, filetype="pdf")[0].get_pixmap(dpi=DPI)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def jst(t):
    j = t + timedelta(hours=9)
    return f"{j.month}/{j.day} {j.hour}時JST ({t:%d}日{t:%H}UTC)"


def valid_time(name):
    # list.json のファイル名の2つ目の14桁が対象時刻(UTC)
    return datetime.strptime(re.findall(r"_(\d{14})_MET", name)[0], "%Y%m%d%H%M%S")


class Fetcher:
    """1回の実行の中で同じ図を2度取りに行かないようにまとめて持つ。"""

    def __init__(self):
        self._list = None

    def wxlist(self):
        if self._list is None:
            self._list = json.loads(get(WXLIST)[0])["asia_monochrome"]
        return self._list

    def asas(self, back):
        t = valid_time(self.wxlist()["now"][-1]) - timedelta(hours=back)
        data, _ = get(f"{WXCHART}{t:%Y%m}/ASAS_MONO_{t:%Y%m%d%H%M}.pdf")
        return pdf_to_image(data), jst(t)

    def fsas(self, ft):
        init = valid_time(self.wxlist()[f"ft{ft}"][-1])
        data, _ = get(f"{WXCHART}FSAS{ft}_MONO_ASIA.pdf")
        return pdf_to_image(data), f"{jst(init + timedelta(hours=ft))} 初期値{init:%d}日{init:%H}UTC"

    def nwp(self, name):
        # 00UTC版と12UTC版のうち、更新が新しい方
        got = []
        for hh in ("00", "12"):
            data, mod = get(f"{NWPMAP}{name}_{hh}.pdf")
            got.append((parsedate_to_datetime(mod), hh, data))
        mod, hh, data = max(got)
        t = mod.astimezone(timezone.utc).replace(hour=int(hh), minute=0, second=0, microsecond=0, tzinfo=None)
        if t > mod.astimezone(timezone.utc).replace(tzinfo=None):
            t -= timedelta(days=1)
        when = jst(t) if name in ANALYSIS else f"初期値 {jst(t)}"
        return pdf_to_image(data), when

    def chart(self, name):
        kind, arg, title = CATALOG[name]
        image, when = getattr(self, kind)(arg)
        return Chart(name, title, when, overlay.apply(name, image))
