"""スキャン請求書から金額を読む（多数決つき）。

Tesseract は1回の読み取りでは信用できない。実物の請求書で測ったところ、
設定を変えた11通りのうち4通りが誤読した（表の罫線を "1" と読み、
376,772 を 3,767,721 にした）。**桁が1つ増えても、見た目は自然な数字になる。**

そこで、同じ場所を**複数の設定で読み、一致したものだけ採用する**。
一致しなければ「読めなかった」として人に回す。読めた数字が
正しいかどうかは、さらに reconcile.py の検算が決める。

  読む（複数回） → 全部一致？ → 検算に通る？ → 採用
                     ↓ いいえ      ↓ いいえ
                    人へ          人へ

外部通信なし。Tesseract はローカルで動く画像認識であり、生成AIではない。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .model import ValidationError

# 読み取り設定。psm 7=1行, 8=1語。倍率2倍は罫線を拾いやすいので入れない
# （実測で 3767721 の誤読を出した）。
VARIANTS = [
    {"psm": 7, "lang": "eng", "whitelist": "0123456789,", "scale": 1},
    {"psm": 7, "lang": "eng", "whitelist": None, "scale": 1},
    {"psm": 8, "lang": "eng", "whitelist": "0123456789,", "scale": 4},
    {"psm": 7, "lang": "eng", "whitelist": "0123456789,", "scale": 4},
]


@dataclass
class CellRead:
    """1つの欄の読み取り結果。"""

    label: str
    value: int | None                  # 全設定が一致したときだけ入る
    votes: dict[int, int] = field(default_factory=dict)
    raw: list[str] = field(default_factory=list)

    @property
    def agreed(self) -> bool:
        return self.value is not None

    @property
    def why(self) -> str:
        if self.agreed:
            return "一致"
        if not self.votes:
            return "数字が読めなかった"
        got = ", ".join(f"{v:,}({n}票)" for v, n in
                        sorted(self.votes.items(), key=lambda x: -x[1]))
        return f"読み取りが割れた: {got}"


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _digits(text: str) -> list[int]:
    out = []
    for m in re.findall(r"\d[\d,. ]*\d|\d", text):
        s = re.sub(r"[,. ]", "", m)
        if s.isdigit():
            out.append(int(s))
    return out


def read_cell(image, box: tuple[int, int, int, int], label: str,
              *, require_unanimous: bool = True) -> CellRead:
    """1つの欄を複数設定で読み、一致した値だけ返す。

    require_unanimous=True のとき、全設定が同じ1つの数字を出した場合のみ
    採用する。1つでも違えば None（＝人に回す）。
    """
    from PIL import Image, ImageOps

    crop = image.crop(box).convert("L")
    votes: Counter[int] = Counter()
    raws: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "cell.png"
        for v in VARIANTS:
            img = crop
            if v["scale"] != 1:
                img = crop.resize((crop.width * v["scale"],
                                   crop.height * v["scale"]))
                img = ImageOps.autocontrast(img).point(
                    lambda p: 0 if p < 140 else 255)
            img.save(tmp)
            cmd = ["tesseract", str(tmp), "stdout",
                   "--psm", str(v["psm"]), "-l", v["lang"]]
            if v["whitelist"]:
                cmd += ["-c", f"tessedit_char_whitelist={v['whitelist']}"]
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=30).stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
            raws.append(out.strip().replace("\n", " "))
            found = _digits(out)
            # 欄に数字が1つだけ写っている前提。複数出たら罫線を拾っている
            if len(found) == 1:
                votes[found[0]] += 1

    value = None
    if votes:
        if require_unanimous:
            if len(votes) == 1 and sum(votes.values()) == len(VARIANTS):
                value = next(iter(votes))
        else:
            top, n = votes.most_common(1)[0]
            if n > len(VARIANTS) / 2:
                value = top

    return CellRead(label=label, value=value, votes=dict(votes), raw=raws)


def read_cells(image_path: str | Path,
               boxes: dict[str, tuple[int, int, int, int]],
               **kw) -> dict[str, CellRead]:
    """テンプレートで決まった複数の欄をまとめて読む。"""
    if not tesseract_available():
        raise ValidationError(
            "tesseract が見つかりません。OCRなしで運用する場合は "
            "金額を手入力してください。")
    from PIL import Image

    image = Image.open(image_path)
    return {label: read_cell(image, box, label, **kw)
            for label, box in boxes.items()}
