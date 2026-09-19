"""手数料負担先の扱い — the one place the two FB-Web routes disagree.

FB-Web offers two ways to submit a 総合振込:

  A. 総合振込 → データ登録 （画面入力 / 金額外部取込CSV）
     For a 先方負担 payee you enter the INVOICE amount and FB-Web subtracts
     the fee itself:  請求金額 10,000 - 手数料 110 = 振込金額 9,890
     (bank manual, 「2．振込金額を入力する」)

  B. 外部ファイル送受信 → 外部ファイル送信 （全銀レコードフォーマット）
     The amount in the file is taken as written. The manual warns:
     「手数料負担先を選択する項目が表示されますが、この項目は変更しないで
      ください。先方を選択すると振込金額が変更される場合があります」

So the SAME 請求金額 must be written differently depending on the route.
Feed a route-A amount into route B and every 先方負担 payee is overpaid by
exactly the fee; feed a route-B amount into route A and they are underpaid
twice over. This module makes the choice explicit and refuses to guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import ValidationError


class Route(str, Enum):
    """How the batch will reach the bank."""

    SCREEN = "screen"    # データ登録 (画面入力 / 金額外部取込) - FB-Web nets the fee
    ZENGIN = "zengin"    # 外部ファイル送信 (全銀) - we must net the fee ourselves


@dataclass(frozen=True)
class FeePolicy:
    """The clinic's 振込手数料 table, as contracted with 鹿児島銀行.

    Deliberately NOT given defaults. A guessed fee silently changes what a
    先方負担 payee receives, and the error is the size of the fee - small
    enough to go unnoticed for months. Fill this in from the bank's 手数料
    schedule (FB-Web top bar → 手数料) and confirm against a real 振込明細.
    """

    same_branch: int          # 同一店内
    same_bank_other_branch: int   # 当行本支店宛
    other_bank: int               # 他行宛
    our_bank_code: str = "0185"
    our_branch_code: str = "107"  # 西陵支店

    def fee_for(self, bank_code: str, branch_code: str) -> int:
        if bank_code != self.our_bank_code:
            return self.other_bank
        if branch_code == self.our_branch_code:
            return self.same_branch
        return self.same_bank_other_branch


def resolve_amount(invoice_total: int, *, fee_borne_by: str, route: Route,
                   policy: FeePolicy | None, bank_code: str,
                   branch_code: str) -> tuple[int, int]:
    """Return (amount_to_write, fee_deducted) for one payee.

    For 当方負担 the written amount is the invoice total under both routes.
    For 先方負担 the written amount depends on the route, per this module's
    docstring.
    """
    if fee_borne_by == "sender":
        return invoice_total, 0

    if fee_borne_by != "beneficiary":
        raise ValidationError(f"fee_borne_by が不正: {fee_borne_by!r}")

    if route is Route.SCREEN:
        # FB-Web subtracts the fee on its side; write the invoice amount.
        return invoice_total, 0

    # Route.ZENGIN - we must net it down ourselves.
    if policy is None:
        raise ValidationError(
            "先方負担の支払先がありますが、手数料テーブル(FeePolicy)が未設定です。"
            "全銀ファイル経路では手数料を自分で差し引く必要があります。"
            "銀行の手数料表を確認して設定してください（推測はしません）。")

    fee = policy.fee_for(bank_code, branch_code)
    net = invoice_total - fee
    if net <= 0:
        raise ValidationError(
            f"請求額 {invoice_total:,}円 から手数料 {fee:,}円 を引くと "
            f"{net:,}円 になります。先方負担の設定を確認してください。")
    return net, fee
