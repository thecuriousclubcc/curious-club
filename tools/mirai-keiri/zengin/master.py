"""振込先マスタ - the single source of truth for bank details.

Bank coordinates NEVER come from an invoice. They come from this file, which a
human populates once per payee from that payee's own 振込先案内 / 通帳 and signs
off on (確認日 / 確認者). An invoice can change what you pay; it can never change
where you pay.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .kana import KanaError, to_zengin_kana
from .model import DEPOSIT_TYPES, ValidationError

REQUIRED_COLUMNS = [
    "payee_id", "display_name", "bank_code", "bank_name_kana",
    "branch_code", "branch_name_kana", "deposit_type", "account_number",
    "payee_name_kana", "fee_borne_by", "verified_on", "verified_by",
]


@dataclass
class Payee:
    payee_id: str
    display_name: str
    bank_code: str
    bank_name_kana: str
    branch_code: str
    branch_name_kana: str
    deposit_type: str
    account_number: str
    payee_name_kana: str
    fee_borne_by: str          # "sender" or "beneficiary"
    verified_on: date | None
    verified_by: str
    conversion_notes: list[str]

    @property
    def is_verified(self) -> bool:
        return self.verified_on is not None and bool(self.verified_by.strip())


def load_payees(path: str | Path) -> dict[str, Payee]:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValidationError(
                f"{path}: 必須列がありません: {', '.join(missing)}")

        payees: dict[str, Payee] = {}
        for lineno, row in enumerate(reader, start=2):
            pid = (row["payee_id"] or "").strip()
            if not pid:
                raise ValidationError(f"{path}:{lineno}: payee_id が空です")
            if pid in payees:
                raise ValidationError(f"{path}:{lineno}: payee_id が重複: {pid}")

            notes: list[str] = []
            raw_name = (row["payee_name_kana"] or "").strip()
            if not raw_name:
                raise ValidationError(f"{path}:{lineno}: {pid}: payee_name_kana が空です")
            try:
                converted = to_zengin_kana(raw_name)
            except KanaError as e:
                raise ValidationError(f"{path}:{lineno}: {pid}: {e}") from e
            notes.extend(converted.notes)

            bank_name = to_zengin_kana((row["bank_name_kana"] or "").strip())
            branch_name = to_zengin_kana((row["branch_name_kana"] or "").strip())

            deposit_type = (row["deposit_type"] or "").strip()
            if deposit_type not in DEPOSIT_TYPES:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: deposit_type が不正: {deposit_type!r} "
                    f"(1=普通 2=当座 4=貯蓄 9=その他)")

            fee = (row["fee_borne_by"] or "sender").strip().lower()
            if fee not in ("sender", "beneficiary"):
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: fee_borne_by は sender / beneficiary: {fee!r}")

            verified_raw = (row["verified_on"] or "").strip()
            verified_on = None
            if verified_raw:
                try:
                    verified_on = datetime.strptime(verified_raw, "%Y-%m-%d").date()
                except ValueError as e:
                    raise ValidationError(
                        f"{path}:{lineno}: {pid}: verified_on は YYYY-MM-DD: "
                        f"{verified_raw!r}") from e

            payees[pid] = Payee(
                payee_id=pid,
                display_name=(row["display_name"] or "").strip(),
                bank_code=(row["bank_code"] or "").strip().zfill(4),
                bank_name_kana=bank_name.text,
                branch_code=(row["branch_code"] or "").strip().zfill(3),
                branch_name_kana=branch_name.text,
                deposit_type=deposit_type,
                account_number=(row["account_number"] or "").strip(),
                payee_name_kana=converted.text,
                fee_borne_by=fee,
                verified_on=verified_on,
                verified_by=(row["verified_by"] or "").strip(),
                conversion_notes=notes,
            )
    return payees
