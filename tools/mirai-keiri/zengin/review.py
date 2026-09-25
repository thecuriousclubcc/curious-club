"""人の確認が要る項目を溜め、確認が済むまで先へ進ませない。

■ 通知の考え方
ポップアップは消される。見落とされる。だから**気づかせる**のではなく
**出さない**。確認待ちが1件でも残っている間は銀行用ファイルを作らない。
経理の方は「ファイルが無い」ことで必ず気づき、画面を開けば理由が書いてある。
見落とせる経路が存在しない。

■ 手入力も同じ関門を通す
「読めなかったから手で入れる」画面は、新しい誤りの入口になる。
手で 3767721 と打てば通る、では意味がない。**手入力した金額も、自動で
読んだ金額とまったく同じ検算（reconcile）と2σ判定を通す。**
このモジュールに、関門を迂回して金額を確定させる経路は無い。

■ 手を入れた記録を残す
誰が・いつ・機械の提案は何で・何に直したか。振込一覧表に印として出し、
承認者が「ここは人が触った」と分かるようにする。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from .history import History
from .model import ValidationError
from .reconcile import InvoiceFigures, reconcile

# 引っかかった理由（経理の方が読む文言）
UNREADABLE = "読み取れない欄があります"
RECONCILE_FAILED = "請求書の中の計算が合いません"
NO_CORROBORATION = "金額を裏づけられません"
OUTLIER = "いつもと金額が違います"
UNKNOWN_PAYEE = "登録されていない支払先です"
AMBIGUOUS_SPLIT = "請求書の切れ目が判断できません"


@dataclass
class Override:
    """人が手を入れた記録。"""

    item_id: str
    who: str
    at: str
    proposed: int | None
    entered: int
    note: str = ""

    def describe(self) -> str:
        p = f"{self.proposed:,}" if self.proposed is not None else "読めず"
        return (f"手入力: {self.who} が {self.at} に "
                f"機械の提案 {p} → {self.entered:,} に修正")


@dataclass
class ReviewItem:
    """人の確認が要る1件。"""

    item_id: str
    payee_id: str
    display_name: str
    reason: str
    figures: InvoiceFigures
    source_pages: list[int] = field(default_factory=list)
    image_path: str = ""
    crop: tuple[int, int, int, int] | None = None
    detail: str = ""
    resolved: bool = False
    override: Override | None = None

    @property
    def proposed_amount(self) -> int | None:
        return self.figures.total_billed

    @property
    def amount(self) -> int | None:
        """確定した金額。未解決なら None。"""
        return self.figures.total_billed if self.resolved else None


class ReviewQueue:
    """確認待ちの箱。空になるまで銀行用ファイルは作らせない。"""

    def __init__(self, items: list[ReviewItem] | None = None,
                 history: History | None = None):
        self._items: dict[str, ReviewItem] = {i.item_id: i for i in (items or [])}
        self._history = history or History()
        self._overrides: list[Override] = []

    def add(self, item: ReviewItem) -> None:
        if item.item_id in self._items:
            raise ValidationError(f"item_id が重複しています: {item.item_id}")
        self._items[item.item_id] = item

    def all(self) -> list[ReviewItem]:
        return list(self._items.values())

    def pending(self) -> list[ReviewItem]:
        return [i for i in self._items.values() if not i.resolved]

    def resolved(self) -> list[ReviewItem]:
        return [i for i in self._items.values() if i.resolved]

    @property
    def is_clear(self) -> bool:
        return not self.pending()

    @property
    def overrides(self) -> list[Override]:
        return list(self._overrides)

    def resolve(self, item_id: str, amount: int, *, who: str,
                note: str = "") -> ReviewItem:
        """人が入れた金額を、自動で読んだ金額と同じ関門に通す。

        通れば確定。通らなければ確定せず、**新しい理由で確認待ちのまま**。
        ここが唯一の確定経路であり、関門を飛ばす引数は用意していない。
        """
        if item_id not in self._items:
            raise ValidationError(f"そのような項目はありません: {item_id}")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise ValidationError("金額は整数（円）で入れてください")
        if amount <= 0:
            raise ValidationError("金額は1円以上にしてください")
        if not who.strip():
            raise ValidationError("入力した人の名前を入れてください")

        item = self._items[item_id]
        proposed = item.proposed_amount

        # 手入力を反映した数字で検算をやり直す
        trial = InvoiceFigures(**{**asdict(item.figures), "total_billed": amount})
        trial.read_by = f"手入力({who})"
        r = reconcile(trial)
        if not r.payable:
            item.reason = RECONCILE_FAILED if r.corroborated else NO_CORROBORATION
            item.detail = "; ".join(r.failures)
            return item

        # 2σ判定も自動と同じように通す
        a = self._history.assess(item.payee_id, amount)
        if a.needs_review:
            item.reason = OUTLIER
            item.detail = "; ".join(a.reasons)
            item.figures = trial
            return item

        item.figures = trial
        item.resolved = True
        item.reason = ""
        item.detail = ""
        item.override = Override(
            item_id=item_id, who=who.strip(),
            at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            proposed=proposed, entered=amount, note=note.strip())
        self._overrides.append(item.override)
        return item

    def force_resolve(self, item_id: str, amount: int, *, who: str,
                      reason: str) -> ReviewItem:
        """2σの警告だけを承知のうえで確定する。

        **検算は飛ばせない。** 2σは「いつもと違う」という注意であって
        誤りの証明ではないため、理由を書けば人の判断で通せる。
        理由は必須で、記録に残り、振込一覧表にも出る。
        """
        if not reason.strip():
            raise ValidationError("いつもと違う金額を通す理由を書いてください")
        item = self._items[item_id]
        trial = InvoiceFigures(**{**asdict(item.figures), "total_billed": amount})
        if not reconcile(trial).payable:
            raise ValidationError(
                "請求書の中の計算が合っていません。これは飛ばせません。")
        item.figures = trial
        item.resolved = True
        item.reason = ""
        item.override = Override(
            item_id=item_id, who=who.strip(),
            at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            proposed=item.proposed_amount, entered=amount,
            note=f"いつもと違う金額を承知で確定: {reason.strip()}")
        self._overrides.append(item.override)
        return item

    def guard_output(self) -> None:
        """銀行用ファイルを作る直前に呼ぶ。確認待ちがあれば止める。"""
        pend = self.pending()
        if pend:
            names = "、".join(i.display_name or i.payee_id for i in pend[:3])
            more = f" ほか{len(pend) - 3}件" if len(pend) > 3 else ""
            raise ValidationError(
                f"確認待ちが {len(pend)}件 残っているため、銀行用ファイルは"
                f"作りません（{names}{more}）。"
                f"確認画面を開いて、すべて処理してください。")

    def save_overrides(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps([asdict(o) for o in self._overrides],
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def summary(self) -> str:
        if self.is_clear:
            n = len(self._items)
            return (f"確認待ちなし（{n}件すべて確認済み）" if n
                    else "確認待ちなし")
        return f"あなたの確認待ち {len(self.pending())}件"
