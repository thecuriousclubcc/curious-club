"""支払履歴にもとづく異常検知（2σ）。

目的は「読み取りが正しいか」ではなく「**いつもと違わないか**」を見ること。
検算（reconcile.py）が捕まえるのは請求書の中で辻褄が合わない誤りだけで、
請求書そのものが正しくても金額が普段と桁違い、という事態は捕まえられない。
そこを履歴で見る。

小標本での注意:
  - 平均±2σ は外れ値に弱い。過去に1回大きな支払があると σ が膨らみ、
    その後の異常を隠してしまう。そこで **中央値＋MAD** による頑健な判定も
    併走させ、**どちらかが反応したら人に回す**。
  - n<3 では統計が成り立たない。「履歴不足」として必ず人に回す。
  - 毎回同額の先（家賃・リース等）は σ=0 になる。この場合は
    「前回と違うこと自体」を異常として扱う。

判定は**止めない**。振込一覧表に印をつけて、承認者の目を向けさせるだけ。
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

MIN_SAMPLES = 3
DEFAULT_SIGMA = 2.0
# 中央値絶対偏差を標準偏差に合わせるための定数（正規分布のとき）
MAD_TO_SIGMA = 1.4826


@dataclass
class Assessment:
    payee_id: str
    amount: int
    verdict: str                      # "ok" / "review"
    reasons: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def needs_review(self) -> bool:
        return self.verdict == "review"


class History:
    """支払先ごとの過去の支払額。

    データの出所は運用で決める（振込一覧表の印刷、会計ソフト、通帳等）。
    **総合振込送信データ一覧には金額の列が無い**ため、そこからは作れない。
    """

    def __init__(self, data: dict[str, list[int]] | None = None):
        self._data: dict[str, list[int]] = {
            k: [int(x) for x in v] for k, v in (data or {}).items()}

    @classmethod
    def load(cls, path: str | Path) -> "History":
        p = Path(path)
        if not p.exists():
            return cls({})
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def amounts(self, payee_id: str) -> list[int]:
        return list(self._data.get(payee_id, []))

    def append(self, payee_id: str, amount: int, *, keep: int = 24) -> None:
        """確定した支払を履歴に足す。直近 keep 件だけ残す。"""
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError("金額は整数（円）で渡してください")
        xs = self._data.setdefault(payee_id, [])
        xs.append(amount)
        del xs[:-keep]

    def assess(self, payee_id: str, amount: int, *,
               sigma: float = DEFAULT_SIGMA,
               min_absolute_yen: int = 0) -> Assessment:
        past = self.amounts(payee_id)
        reasons: list[str] = []
        stats: dict = {"n": len(past)}

        if not past:
            return Assessment(payee_id, amount, "review",
                              [f"初回の支払先です（{amount:,}円）"], stats)

        if len(past) < MIN_SAMPLES:
            return Assessment(
                payee_id, amount, "review",
                [f"履歴が{len(past)}件しかなく統計判定ができません"
                 f"（今回 {amount:,}円 / 過去 "
                 f"{', '.join(f'{x:,}' for x in past)}）"], stats)

        mean = statistics.fmean(past)
        median = statistics.median(past)
        sd = statistics.stdev(past)          # 標本標準偏差
        stats.update(mean=mean, median=median, sd=sd)

        diff = amount - median
        if abs(diff) < min_absolute_yen:
            return Assessment(payee_id, amount, "ok", [], stats)

        # 毎回同額だった先
        if sd == 0:
            if amount != past[-1]:
                reasons.append(
                    f"毎回同額（{past[-1]:,}円）でしたが今回 {amount:,}円 です"
                    f"（{diff:+,}円）")
            return Assessment(payee_id, amount,
                              "review" if reasons else "ok", reasons, stats)

        # 平均±2σ
        z = (amount - mean) / sd
        stats["z"] = z
        if abs(z) >= sigma:
            direction = "高い" if z > 0 else "低い"
            reasons.append(
                f"過去平均 {mean:,.0f}円（σ={sd:,.0f}）に対し今回 {amount:,}円 — "
                f"{abs(z):.1f}σ {direction}（{amount - mean:+,.0f}円）")

        # 中央値＋MAD（外れ値に強い判定）
        mad = statistics.median([abs(x - median) for x in past])
        stats["mad"] = mad
        if mad > 0:
            rz = (amount - median) / (mad * MAD_TO_SIGMA)
            stats["robust_z"] = rz
            if abs(rz) >= sigma and not reasons:
                direction = "高い" if rz > 0 else "低い"
                reasons.append(
                    f"中央値 {median:,.0f}円 から {abs(rz):.1f}σ 相当 {direction}"
                    f"（今回 {amount:,}円 / {diff:+,}円）"
                    f"— 過去の大きな支払で平均がぶれているため中央値で判定")
        elif amount != median:
            reasons.append(
                f"過去はほぼ {median:,.0f}円 で一定でしたが今回 {amount:,}円 です"
                f"（{diff:+,}円）")

        return Assessment(payee_id, amount,
                          "review" if reasons else "ok", reasons, stats)


def assess_batch(payments, history: History, **kw) -> list[Assessment]:
    """バッチ全体を判定する。ok のものも返す（件数を数えたいため）。"""
    return [history.assess(p.payee_id, p.amount, **kw) for p in payments]
