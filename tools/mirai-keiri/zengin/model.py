"""Data model for a 総合振込 (general transfer) run.

Amounts are integer yen everywhere. Floats are never used: a float cent-error
on a bank transfer is unrecoverable once the file is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# 預金種目 (deposit type) codes, per 全銀協規定形式.
DEPOSIT_TYPES = {
    "1": "普通",
    "2": "当座",
    "4": "貯蓄",
    "9": "その他",
}

# 新規コード (record status).
NEW_CODES = {
    "0": "その他",
    "1": "第1回",
    "2": "変更",
}

# 振込指定区分.
TRANSFER_KINDS = {
    "7": "テレ振込",
    "8": "文書振込",
    " ": "指定なし",
}

# 識別表示 (data record byte 113).
#   "Y"   = EDI情報を使用する。このとき項番12・13（顧客コード1・2, bytes
#           92-111）は 20桁の EDI情報として再解釈される。
#   space = EDI情報を使用しない。項番12・13は顧客コードのまま。
# 手数料負担先はこの項目ではない。全銀フォーマットに振込手数料の項目は
# 存在せず、先方負担はアップロード画面側で指定し、ファイル内の全明細に
# 一括適用される（FB-Web 外部ファイル送信も同様）。
EDI_IN_USE = "Y"
EDI_NOT_USED = " "


class ValidationError(ValueError):
    """Raised when data cannot produce a byte-correct Zengin file."""


@dataclass(frozen=True)
class Requester:
    """委託者 - the clinic, as registered with 鹿児島銀行."""

    consignor_code: str      # 委託者コード (10) - issued by the bank
    name_kana: str           # 委託者名 (40)
    bank_code: str           # 仕向銀行番号 (4)  e.g. "0185"
    bank_name_kana: str      # 仕向銀行名 (15)
    branch_code: str         # 仕向支店番号 (3)
    branch_name_kana: str    # 仕向支店名 (15)
    deposit_type: str        # 預金種目 (1)
    account_number: str      # 口座番号 (7)

    def validate(self) -> None:
        if not self.consignor_code.isdigit() or len(self.consignor_code) > 10:
            raise ValidationError(f"委託者コードが不正: {self.consignor_code!r}")
        if not (self.bank_code.isdigit() and len(self.bank_code) == 4):
            raise ValidationError(f"仕向銀行番号は4桁の数字: {self.bank_code!r}")
        if not (self.branch_code.isdigit() and len(self.branch_code) == 3):
            raise ValidationError(f"仕向支店番号は3桁の数字: {self.branch_code!r}")
        if self.deposit_type not in DEPOSIT_TYPES:
            raise ValidationError(f"預金種目が不正: {self.deposit_type!r}")
        if not self.account_number.isdigit() or len(self.account_number) > 7:
            raise ValidationError(f"口座番号が不正: {self.account_number!r}")


@dataclass
class Payment:
    """One データレコード - one transfer to one stakeholder."""

    payee_id: str                 # internal master key, not written to the file
    bank_code: str                # 被仕向銀行番号 (4)
    bank_name_kana: str           # 被仕向銀行名 (15)
    branch_code: str              # 被仕向支店番号 (3)
    branch_name_kana: str         # 被仕向支店名 (15)
    deposit_type: str             # 預金種目 (1)
    account_number: str           # 口座番号 (7)
    payee_name_kana: str          # 受取人名 (30)
    amount: int                   # 振込金額 (10) - integer yen
    new_code: str = "0"           # 新規コード (1)
    customer_code_1: str = ""     # 顧客コード1 (10)
    customer_code_2: str = ""     # 顧客コード2 (10)
    transfer_kind: str = "7"      # 振込指定区分 (1) 7=電信振込（実績値）
    edi_info: str = ""            # 識別表示="Y" のとき 顧客コード欄に入る20桁

    # Provenance - carried into the review sheet, never into the bank file.
    payee_name_display: str = ""
    source_documents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not (self.bank_code.isdigit() and len(self.bank_code) == 4):
            raise ValidationError(
                f"{self.payee_id}: 被仕向銀行番号は4桁の数字: {self.bank_code!r}")
        if not (self.branch_code.isdigit() and len(self.branch_code) == 3):
            raise ValidationError(
                f"{self.payee_id}: 被仕向支店番号は3桁の数字: {self.branch_code!r}")
        if self.deposit_type not in DEPOSIT_TYPES:
            raise ValidationError(
                f"{self.payee_id}: 預金種目が不正: {self.deposit_type!r}")
        if not self.account_number.isdigit() or not (1 <= len(self.account_number) <= 7):
            raise ValidationError(
                f"{self.payee_id}: 口座番号が不正: {self.account_number!r}")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise ValidationError(
                f"{self.payee_id}: 振込金額は整数でなければなりません: {self.amount!r}")
        if self.amount <= 0:
            raise ValidationError(
                f"{self.payee_id}: 振込金額は1円以上: {self.amount}")
        if self.amount > 9_999_999_999:
            raise ValidationError(
                f"{self.payee_id}: 振込金額が10桁を超えています: {self.amount}")
        if self.new_code not in NEW_CODES:
            raise ValidationError(
                f"{self.payee_id}: 新規コードが不正: {self.new_code!r}")
        if self.transfer_kind not in TRANSFER_KINDS:
            raise ValidationError(
                f"{self.payee_id}: 振込指定区分が不正: {self.transfer_kind!r}")
        if self.edi_info:
            if self.customer_code_1 or self.customer_code_2:
                raise ValidationError(
                    f"{self.payee_id}: EDI情報と顧客コードは同じ領域(92-111)を"
                    f"使うため併用できません。どちらか一方にしてください。")
            if len(self.edi_info.encode("cp932")) > 20:
                raise ValidationError(
                    f"{self.payee_id}: EDI情報が20桁を超えています: "
                    f"{self.edi_info!r}")

    @property
    def identifier(self) -> str:
        """識別表示 (byte 113)."""
        return EDI_IN_USE if self.edi_info else EDI_NOT_USED


@dataclass
class TransferBatch:
    """A whole 総合振込 file: one header, N data records, trailer, end."""

    requester: Requester
    transfer_date: date          # 取組日 - the value date at the bank
    payments: list[Payment] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.payments)

    @property
    def total_amount(self) -> int:
        return sum(p.amount for p in self.payments)

    def validate(self) -> None:
        self.requester.validate()
        if not self.payments:
            raise ValidationError("振込明細が0件です")
        if self.total_count > 999_999:
            raise ValidationError(f"件数が6桁を超えています: {self.total_count}")
        if self.total_amount > 999_999_999_999:
            raise ValidationError(f"合計金額が12桁を超えています: {self.total_amount}")
        for p in self.payments:
            p.validate()
