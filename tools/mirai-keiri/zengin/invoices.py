"""Invoice intake and aggregation.

An "invoice row" is the normalised result of reading one 請求書. How that row is
produced (per-vendor template parser, manual entry, an OCR pass) is out of scope
here on purpose: this module only ever sees payee_id + amount + provenance, so
the money path stays identical regardless of how the document was read.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .model import Payment, ValidationError
from .master import Payee

REQUIRED_COLUMNS = ["payee_id", "invoice_no", "invoice_date",
                    "amount", "source_file"]


@dataclass
class InvoiceRow:
    payee_id: str
    invoice_no: str
    invoice_date: date
    amount: int
    source_file: str
    memo: str = ""


@dataclass
class Anomaly:
    payee_id: str
    kind: str
    message: str


def load_invoices(path: str | Path) -> list[InvoiceRow]:
    path = Path(path)
    rows: list[InvoiceRow] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValidationError(f"{path}: 必須列がありません: {', '.join(missing)}")

        for lineno, row in enumerate(reader, start=2):
            pid = (row["payee_id"] or "").strip()
            inv_no = (row["invoice_no"] or "").strip()
            if not pid:
                raise ValidationError(f"{path}:{lineno}: payee_id が空です")

            key = (pid, inv_no)
            if inv_no and key in seen:
                raise ValidationError(
                    f"{path}:{lineno}: 請求書番号が重複しています: {pid} / {inv_no}。"
                    f"二重振込を防ぐため処理を中止します。")
            seen.add(key)

            raw_amount = (row["amount"] or "").strip().replace(",", "").replace("\\", "")
            raw_amount = raw_amount.replace("¥", "").replace("円", "")
            try:
                amount = int(raw_amount)
            except ValueError as e:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: amount が整数ではありません: "
                    f"{row['amount']!r}") from e

            raw_date = (row["invoice_date"] or "").strip()
            try:
                inv_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError as e:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: invoice_date は YYYY-MM-DD: "
                    f"{raw_date!r}") from e

            rows.append(InvoiceRow(
                payee_id=pid, invoice_no=inv_no, invoice_date=inv_date,
                amount=amount, source_file=(row["source_file"] or "").strip(),
                memo=(row.get("memo") or "").strip(),
            ))
    return rows


def detect_anomalies(rows: list[InvoiceRow],
                     history: dict[str, list[int]] | None = None,
                     *, sigma: float = 2.0) -> list[Anomaly]:
    """Flag rows that need a human's eyes before the file is built.

    Pure arithmetic - no model, no inference. A flag never blocks the run by
    itself; it marks the row in the review sheet so the approver looks at it.
    """
    out: list[Anomaly] = []
    history = history or {}

    totals: dict[str, int] = {}
    for r in rows:
        totals[r.payee_id] = totals.get(r.payee_id, 0) + r.amount

    for r in rows:
        if r.amount <= 0:
            out.append(Anomaly(r.payee_id, "amount",
                               f"請求額が0以下です ({r.amount:,}円 / {r.invoice_no})"))

    for pid, total in totals.items():
        past = history.get(pid) or []
        if len(past) < 3:
            if not past:
                out.append(Anomaly(pid, "new_payee",
                                   f"初回の支払先です（履歴なし・{total:,}円）"))
            continue
        mean = statistics.fmean(past)
        sd = statistics.pstdev(past)
        if sd == 0:
            if total != past[-1]:
                out.append(Anomaly(
                    pid, "changed",
                    f"毎回同額（{past[-1]:,}円）でしたが今回 {total:,}円 です"))
            continue
        z = (total - mean) / sd
        if abs(z) >= sigma:
            out.append(Anomaly(
                pid, "outlier",
                f"過去平均 {mean:,.0f}円 (σ={sd:,.0f}) に対し今回 {total:,}円 "
                f"— {z:+.1f}σ の乖離"))

    return out


def aggregate(rows: list[InvoiceRow], payees: dict[str, Payee],
              *, require_verified: bool = True,
              route=None, fee_policy=None) -> list[Payment]:
    """Group invoice rows into one Payment per payee.

    `route` decides how a 先方負担 fee is handled (see zengin.fees); it
    defaults to the 全銀 file route, which nets the fee here.
    """
    from .fees import Route, resolve_amount
    from .model import FEE_BORNE_BY_BENEFICIARY, FEE_BORNE_BY_SENDER

    if route is None:
        route = Route.ZENGIN

    grouped: dict[str, list[InvoiceRow]] = {}
    for r in rows:
        grouped.setdefault(r.payee_id, []).append(r)

    payments: list[Payment] = []
    for pid in sorted(grouped):
        if pid not in payees:
            raise ValidationError(
                f"振込先マスタに payee_id {pid!r} がありません。"
                f"マスタに登録し、口座を人が確認してから再実行してください。")
        p = payees[pid]
        if require_verified and not p.is_verified:
            raise ValidationError(
                f"{pid} ({p.display_name}): 口座の確認欄 (verified_on / verified_by) "
                f"が空です。未確認の口座には振り込めません。")

        items = grouped[pid]
        invoice_total = sum(i.amount for i in items)
        total, fee = resolve_amount(
            invoice_total, fee_borne_by=p.fee_borne_by, route=route,
            policy=fee_policy, bank_code=p.bank_code,
            branch_code=p.branch_code)
        extra_notes = []
        if fee:
            extra_notes.append(
                f"先方負担: 請求 {invoice_total:,}円 − 手数料 {fee:,}円 "
                f"= 振込 {total:,}円")
        payments.append(Payment(
            payee_id=pid,
            bank_code=p.bank_code,
            bank_name_kana=p.bank_name_kana,
            branch_code=p.branch_code,
            branch_name_kana=p.branch_name_kana,
            deposit_type=p.deposit_type,
            account_number=p.account_number,
            payee_name_kana=p.payee_name_kana,
            amount=total,
            fee_flag=(FEE_BORNE_BY_BENEFICIARY if p.fee_borne_by == "beneficiary"
                      else FEE_BORNE_BY_SENDER),
            payee_name_display=p.display_name,
            source_documents=[i.source_file for i in items if i.source_file],
            notes=list(p.conversion_notes) + extra_notes,
        ))
    return payments
