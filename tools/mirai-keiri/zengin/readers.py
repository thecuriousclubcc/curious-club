"""読み取り器の差し替え口と、二重読みによる合意判定。

**読み取り器は信用しない。合意と検算を信用する。**

Tesseract も VLM も、単独では桁を誤る。実測で Tesseract は設定違い11通り中
4通りが誤読した（罫線を "1" と読み 376,772 → 3,767,721）。VLM も数字の
読み違いが知られている。どちらも「もっともらしい間違った数字」を出す。

そこで **仕組みの違う2つの読み手に同じ欄を読ませ、一致したときだけ採用**する。
Tesseract（パターン認識）と VLM（生成モデル）は誤り方が違うので、
同じ間違いを同時に起こす確率は、片方が間違う確率よりずっと低い。

    Tesseract ─┐
               ├→ 一致した？ ─Yes→ 検算 ─通った→ 2σ判定 ─→ 採用
    VLM       ─┘      │No                │不通                │外れ
                      ↓                  ↓                    ↓
                     人へ                人へ              印をつけて人へ

VLM は localhost の Ollama のみ。データは機内から出ない。
（tests/test_offline_guarantee.py が URL を機械検査する）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from .model import ValidationError
from .ocr import _digits

# Ollama のローカル既定。ここ以外を指せないよう、テストで検査している。
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


class FieldReader(Protocol):
    """1つの欄から数字の候補を返すもの。"""

    name: str

    def read(self, image_path: str, box: tuple[int, int, int, int],
             label: str) -> list[int]:
        ...


@dataclass
class TesseractReader:
    """既存の多数決OCR。設定違いで複数回読み、全一致した値だけ返す。"""

    name: str = "tesseract"

    def read(self, image_path, box, label) -> list[int]:
        from PIL import Image
        from .ocr import read_cell
        r = read_cell(Image.open(image_path), box, label)
        return [r.value] if r.agreed else []


@dataclass
class OllamaVisionReader:
    """localhost の Ollama で画像から数字を読む。

    **この実装は未検証である。** 開発環境から Ollama のモデルを取得できず
    （ollama.com / registry.ollama.ai / huggingface.co が遮断）、精度を
    measure.py で実測していない。院内で実データにかけて測ること。
    精度が出なくても安全性は変わらない（合意・検算・2σ が効くため）が、
    自動で通る率は変わる。
    """

    model: str = "qwen2.5vl:3b"
    name: str = "ollama"
    timeout: int = 120
    attempts: int = 2          # 同じ画像を複数回読ませ、揺れを検出する

    PROMPT = (
        "この画像は請求書の金額欄を切り出したものです。"
        "写っている数字を、そのまま1つだけ半角数字で答えてください。"
        "カンマ・円記号・説明は書かず、数字だけを出力してください。"
        "読み取れない場合は UNKNOWN とだけ答えてください。"
    )

    def read(self, image_path, box, label) -> list[int]:
        import base64
        import io
        import urllib.request
        from PIL import Image

        buf = io.BytesIO()
        Image.open(image_path).crop(box).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        seen: list[int] = []
        for _ in range(self.attempts):
            payload = json.dumps({
                "model": self.model, "prompt": self.PROMPT,
                "images": [b64], "stream": False,
                "options": {"temperature": 0},
            }).encode()
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = json.loads(r.read().decode())
            except Exception as e:                     # noqa: BLE001
                raise ValidationError(
                    f"Ollama に接続できません（{OLLAMA_URL}）: {e}。"
                    f"`ollama serve` が動いているか確認してください。") from e
            found = _digits(body.get("response", ""))
            if len(found) == 1:
                seen.append(found[0])

        # 複数回読んで揺れたら採用しない
        if len(seen) == self.attempts and len(set(seen)) == 1:
            return [seen[0]]
        return []


@dataclass
class CrossRead:
    label: str
    value: int | None
    per_reader: dict[str, list[int]] = field(default_factory=dict)

    @property
    def agreed(self) -> bool:
        return self.value is not None

    @property
    def why(self) -> str:
        if self.agreed:
            return "両方が一致"
        parts = []
        for name, vals in self.per_reader.items():
            parts.append(f"{name}={vals[0]:,}" if vals else f"{name}=読めず")
        return "不一致: " + " / ".join(parts)


def cross_read(image_path: str, box: tuple[int, int, int, int], label: str,
               readers: list[FieldReader]) -> CrossRead:
    """複数の読み手に同じ欄を読ませ、**全員が同じ1つの数字**を出した時だけ採用。

    1人でも読めなかった、または食い違ったら None（＝人へ）。
    読み手を増やすほど自動通過率は下がり、安全側に倒れる。
    """
    if not readers:
        raise ValidationError("読み取り器が指定されていません")

    per: dict[str, list[int]] = {}
    for r in readers:
        per[r.name] = r.read(image_path, box, label)

    values = [v[0] for v in per.values() if len(v) == 1]
    ok = len(values) == len(readers) and len(set(values)) == 1
    return CrossRead(label=label, value=values[0] if ok else None,
                     per_reader=per)
