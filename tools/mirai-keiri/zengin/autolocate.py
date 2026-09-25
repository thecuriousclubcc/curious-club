"""見出しから金額の欄を推定する試み。**現時点では実用にならない。**

■ 測定結果（実物2業者・2026-09-25）
    アイティーアイ  7欄中4欄が一致。買上額と消費税額が1列ずれた
    アステム        7欄中0欄が一致。まったく当たらない

**この方法では請求書を自動で読めない。テンプレートが必要である。**
アステムの表は値が縦に積まれ、見出しと値の位置関係が右でも真下でもないため、
見出しからの相対位置という前提自体が成り立たなかった。

■ それでも残している理由
1. **字体の吸収（CJK_VARIANTS）は独立して必要。** RapidOCR は中国語モデルなので
   日本語の見出しを中国語字体で返す（今回御請求額 → 今回御請求"额"）。
   日本語の見出しを扱うどの処理でも必要になる。
2. **テンプレートを人が作るときの下書きに使える。** 候補の座標を出して人が
   直す用途なら、外れても費用は人の一手間で済む。
3. **安全側の設計が効くことの証拠になる。** 系統的に誤った読み取り器を
   与えても、検算が両方の失敗を捕まえた（tests に固定してある）。

■ 絶対にやらないこと
**この推定を金額の確定に使わない。** パイプラインには繋いでいない。
使う場合も結果は必ず検算を通す。

■ 字体の吸収
RapidOCR は中国語モデルのため、日本語の見出しを中国語字体で返す
（今回御請求額 → 今回御請求"额"、今回合計金額 → 今回"合计金额"）。
そのままでは照合が一致しないので、字体を寄せてから突き合わせる。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# RapidOCR が返す中国語字体 → 日本語字体
CJK_VARIANTS = str.maketrans({
    "额": "額", "费": "費", "计": "計", "见": "見", "岛": "島", "银": "銀",
    "达": "達", "羲": "義", "样": "様", "樣": "様", "别": "別", "预": "預",
    "买": "買", "卖": "売", "贩": "販", "单": "単", "数": "数", "价": "価",
    "结": "結", "总": "総", "额": "額", "务": "務", "关": "関", "运": "運",
    "输": "輸", "报": "報", "书": "書", "记": "記", "检": "検", "查": "査",
    "杳": "査", "収": "収", "涼": "額",
})

# 欄の名前 → その見出しとして現れうる語（前方一致で使う）
FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "今回御請求額": ("今回御請求額", "今回ご請求額", "ご請求額", "御請求額",
                     "請求金額", "請求額", "合計請求額", "今回請求額"),
    "今回御買上額": ("今回御買上額", "今回お買い上げ額", "今回買上額",
                     "今回御買上", "今回買上"),
    "今回消費税額": ("今回消費税額", "今回消費税等", "消費税額", "消費税等"),
    "今回合計金額": ("今回合計金額", "今回合計額", "合計金額", "合計額"),
    "前回御請求額": ("前回御請求額", "前回ご請求額", "前回請求額"),
    "御入金額": ("御入金額", "ご入金額", "入金額"),
    "繰越額": ("繰越額", "繰越金額", "繰越"),
}


@dataclass
class TextBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def normalised(self) -> str:
        return self.text.translate(CJK_VARIANTS)

    @property
    def as_int(self) -> int | None:
        s = re.sub(r"[^\d]", "", self.text)
        return int(s) if s and len(s) <= 12 else None


def to_boxes(rapid_result) -> list[TextBox]:
    out: list[TextBox] = []
    for r in (rapid_result or []):
        xs = [p[0] for p in r[0]]
        ys = [p[1] for p in r[0]]
        out.append(TextBox(str(r[1]), min(xs), min(ys), max(xs), max(ys),
                           float(r[2])))
    return out


def find_label(boxes: list[TextBox], field: str) -> TextBox | None:
    """見出しを探す。より長い語に一致したものを優先する。

    「請求額」より「今回御請求額」を先に採る。短い語だけで当てると
    「前回御請求額」を拾ってしまう。
    """
    best: tuple[int, TextBox] | None = None
    for cand in FIELD_LABELS.get(field, ()):
        for b in boxes:
            if cand in b.normalised:
                if best is None or len(cand) > best[0]:
                    best = (len(cand), b)
    return best[1] if best else None


def value_near(boxes: list[TextBox], label: TextBox, *,
               row_tolerance: float = 0.9,
               max_below: float = 3.0) -> TextBox | None:
    """見出しに対応する数字を選ぶ。

    日本語の帳票では、値は見出しの **右** か **すぐ下** にある。
    1. 同じ行（縦位置が見出しと重なる）で、右にある最も近い数字
    2. 無ければ、真下（横位置が重なる）で最も近い数字
    どちらも無ければ None。**無理に当てない。**
    """
    h = max(label.y1 - label.y0, 1.0)

    same_row = [b for b in boxes
                if b.as_int is not None
                and abs(b.cy - label.cy) <= h * row_tolerance
                and b.x0 >= label.x1 - h * 0.3]
    if same_row:
        return min(same_row, key=lambda b: b.x0 - label.x1)

    below = [b for b in boxes
             if b.as_int is not None
             and b.cy > label.y1
             and b.cy - label.y1 <= h * max_below
             and b.x1 > label.x0 - h and b.x0 < label.x1 + h * 4]
    if below:
        return min(below, key=lambda b: b.cy - label.y1)
    return None


def locate_fields(rapid_result, fields: tuple[str, ...] = ()
                  ) -> dict[str, int | None]:
    """ページ全体の読み取り結果から、欄ごとの金額を推定する。

    当たらなかった欄は None。**推測で埋めない。**
    """
    boxes = to_boxes(rapid_result)
    wanted = fields or tuple(FIELD_LABELS)
    out: dict[str, int | None] = {}
    for f in wanted:
        lab = find_label(boxes, f)
        if lab is None:
            out[f] = None
            continue
        v = value_near(boxes, lab)
        out[f] = v.as_int if v else None
    return out
