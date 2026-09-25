"""請求書の自己検算。

請求書に書かれた数字は互いに整合している。読み取り手（OCR・LLM・人）が
何であっても、読んだ結果が正しいかは**計算で判定できる**。

    繰越額     = 前回御請求額 − 御入金額
    今回合計額 = 今回御買上額 + 今回消費税額
    今回御請求額 = 繰越額 + 今回合計金額
    今回消費税額 ≈ 今回御買上額 × 税率

この検算に通らない読み取りは、読み手が誰であれ採用しない。
**読み取り器は提案するだけで、合否はここが決める。**

これにより、抽出に OCR を使おうとローカルLLMを使おうと、誤った金額が
振込データに入る経路がなくなる。LLMを使う場合でも、LLMは
「どの数字がどの項目か」を提案するだけで、最終判断は持たない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .model import ValidationError


@dataclass
class InvoiceFigures:
    """請求書の表から読み取った数字。すべて整数（円）。

    読み取れなかった項目は None。None の項目に関わる検算は
    「検算できない」として扱い、勝手に補完しない。
    """

    previous_billed: int | None = None    # 前回御請求額
    payment_received: int | None = None   # 御入金額
    carried_over: int | None = None       # 繰越額
    purchases: int | None = None          # 今回御買上額
    tax: int | None = None                # 今回消費税額
    subtotal: int | None = None           # 今回合計金額
    total_billed: int | None = None       # 今回御請求額  ← 実際に払う額

    source_file: str = ""
    read_by: str = ""                     # "ocr" / "llm" / "manual" など
    line_items_total: int | None = None   # 明細の金額合計（取れた場合）


@dataclass
class ReconcileResult:
    ok: bool
    checked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def payable(self) -> bool:
        """自動で先に進めてよいか。ひとつでも不整合なら人に上げる。"""
        return self.ok and not self.failures


def reconcile(f: InvoiceFigures, *, tax_rate: str = "0.10",
              tax_tolerance: int = 1) -> ReconcileResult:
    """請求書内部の整合をとる。

    tax_tolerance: 消費税の端数処理（切捨/四捨五入）が業者ごとに違うため、
    ±1円までは許容する。2円以上ずれたら読み取り誤りとみなす。
    """
    checked: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []

    def check(label: str, got, want) -> None:
        if got is None or want is None:
            skipped.append(label)
            return
        checked.append(label)
        if got != want:
            failures.append(f"{label}: 記載 {got:,} ≠ 計算 {want:,} "
                            f"(差 {got - want:+,})")

    # 繰越額 = 前回御請求額 − 御入金額
    if f.previous_billed is not None and f.payment_received is not None:
        check("繰越額", f.carried_over, f.previous_billed - f.payment_received)
    else:
        skipped.append("繰越額")

    # 今回合計金額 = 今回御買上額 + 今回消費税額
    if f.purchases is not None and f.tax is not None:
        check("今回合計金額", f.subtotal, f.purchases + f.tax)
    else:
        skipped.append("今回合計金額")

    # 今回御請求額 = 繰越額 + 今回合計金額
    if f.carried_over is not None and f.subtotal is not None:
        check("今回御請求額", f.total_billed, f.carried_over + f.subtotal)
    else:
        skipped.append("今回御請求額")

    # 消費税 ≈ 買上額 × 税率（端数処理の差は許容）
    if f.purchases is not None and f.tax is not None:
        expected = int(Decimal(f.purchases) * Decimal(tax_rate))
        checked.append("消費税率")
        if abs(f.tax - expected) > tax_tolerance:
            failures.append(
                f"消費税率: 記載 {f.tax:,} ≠ {f.purchases:,}×{tax_rate} "
                f"≈ {expected:,} (差 {f.tax - expected:+,})")
    else:
        skipped.append("消費税率")

    # 明細合計 = 今回御買上額
    if f.line_items_total is not None and f.purchases is not None:
        check("明細合計", f.line_items_total, f.purchases)
    else:
        skipped.append("明細合計")

    # 実際に払う額が取れていなければ、そもそも先へ進めない。
    if f.total_billed is None:
        failures.append("今回御請求額が読み取れていません")
    elif f.total_billed < 0:
        failures.append(f"今回御請求額が負です: {f.total_billed:,}")

    return ReconcileResult(ok=not failures, checked=checked,
                           skipped=skipped, failures=failures)


def accept_or_raise(f: InvoiceFigures, **kw) -> int:
    """検算に通れば支払額を返す。通らなければ止める。

    読み取り器が OCR でもLLMでも人でも、通る条件は同じ。
    読み手を信用するのではなく、数字の整合を信用する。
    """
    r = reconcile(f, **kw)
    if not r.payable:
        detail = "; ".join(r.failures)
        raise ValidationError(
            f"{f.source_file or '請求書'}: 検算が合いません（読み取り={f.read_by or '不明'}）"
            f" — {detail}。人が確認してください。")
    return f.total_billed  # type: ignore[return-value]
