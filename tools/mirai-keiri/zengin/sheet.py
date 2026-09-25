"""振込一覧表 - the sheet a human approves before anything reaches the bank.

This is the control point. It shows, for every payee: which invoice files the
amount came from, the exact bytes that will sit in the 受取人名 field, any
transformation applied to the name, and any anomaly flag. The grand total on
this sheet is the same integer written into the trailer record, so approving
the sheet is equivalent to approving the file.
"""

from __future__ import annotations

from datetime import date

from .invoices import Anomaly, InvoiceRow
from .model import DEPOSIT_TYPES, TransferBatch
from .xlsx import (STYLE_HEADER, STYLE_YEN, STYLE_YEN_BOLD, write_xlsx)

SHEET_HEADERS = [
    "No", "支払先ID", "支払先名", "金融機関", "支店", "種目",
    "口座番号", "受取人名(半角カナ)", "カナ桁数", "振込金額",
    "手数料", "請求書件数", "請求書ファイル", "確認事項",
]

COL_WIDTHS = [5, 12, 26, 16, 14, 6, 11, 32, 9, 14, 12, 11, 40, 40]


def build_rows(batch: TransferBatch, invoices: list[InvoiceRow],
               anomalies: list[Anomaly]) -> tuple[list[list], list[list[int]]]:
    by_payee: dict[str, list[InvoiceRow]] = {}
    for r in invoices:
        by_payee.setdefault(r.payee_id, []).append(r)

    flags: dict[str, list[str]] = {}
    for a in anomalies:
        flags.setdefault(a.payee_id, []).append(a.message)

    rows: list[list] = []
    styles: list[list[int]] = []

    title = (f"総合振込 振込一覧表 — 取組日 "
             f"{batch.transfer_date.strftime('%Y-%m-%d')}")
    rows.append([title])
    styles.append([STYLE_HEADER])
    rows.append([])
    styles.append([])

    rows.append(list(SHEET_HEADERS))
    styles.append([STYLE_HEADER] * len(SHEET_HEADERS))

    for i, p in enumerate(batch.payments, 1):
        items = by_payee.get(p.payee_id, [])
        note_parts = list(p.notes) + flags.get(p.payee_id, [])
        rows.append([
            i,
            p.payee_id,
            p.payee_name_display,
            f"{p.bank_code} {p.bank_name_kana}",
            f"{p.branch_code} {p.branch_name_kana}",
            DEPOSIT_TYPES.get(p.deposit_type, p.deposit_type),
            p.account_number,
            p.payee_name_kana,
            len(p.payee_name_kana.encode("cp932")),
            p.amount,
            next((n.split(":")[0] for n in p.notes if n.startswith("先方負担")),
                 "当方負担"),
            len(items),
            " / ".join(sorted({r.source_file for r in items if r.source_file})),
            " / ".join(note_parts),
        ])
        style_row = [0] * len(SHEET_HEADERS)
        style_row[9] = STYLE_YEN
        styles.append(style_row)

    rows.append([])
    styles.append([])

    total_row: list = [""] * len(SHEET_HEADERS)
    total_row[0] = "合計"
    total_row[8] = f"{batch.total_count} 件"
    total_row[9] = batch.total_amount
    rows.append(total_row)
    total_styles = [STYLE_HEADER] * len(SHEET_HEADERS)
    total_styles[9] = STYLE_YEN_BOLD
    styles.append(total_styles)

    rows.append([])
    styles.append([])
    rows.append(["承認欄", "確認者:", "", "承認者:", "", "承認日:", ""])
    styles.append([STYLE_HEADER, 0, 0, 0, 0, 0, 0])

    return rows, styles


def write_review_sheet(path: str, batch: TransferBatch,
                       invoices: list[InvoiceRow],
                       anomalies: list[Anomaly]) -> None:
    rows, styles = build_rows(batch, invoices, anomalies)
    write_xlsx(path, rows, sheet_name="振込一覧", styles=styles,
               col_widths=COL_WIDTHS)
