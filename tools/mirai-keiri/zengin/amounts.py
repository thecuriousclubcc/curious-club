"""金額取込用CSVの「素材」を出す。

FB-Web の［金額外部取込］が要求するCSVの列仕様は**まだ不明**（ONSITE.md ②）。
仕様が分かる前に列順を決め打ちするのは推測なので、ここではやらない。

代わりに、**照合キーになりうる列を全部持った1枚**を出す。現場で本物の仕様が
判明したら、必要な列を抜いて並べ替えるだけで取込用CSVになる。
データを作り直す必要はなく、作業は列の選択と並べ替えに閉じる。

列:
    payee_id, 顧客コード1(10桁正規化), 顧客コード1(原文), 顧客コード2,
    金融機関コード, 支店コード, 預金種目, 口座番号, 受取人名カナ,
    金額, 手数料負担先, 請求書件数, 突合キー(口座自然キー)
"""

from __future__ import annotations

import csv
from pathlib import Path

from .custcode import account_key, normalize_code

AMOUNT_SOURCE_HEADERS = [
    "payee_id",
    "顧客コード1_10桁",
    "顧客コード1_原文",
    "顧客コード2_10桁",
    "金融機関コード",
    "支店コード",
    "預金種目",
    "口座番号",
    "受取人名カナ",
    "金額",
    "手数料負担先",
    "請求書件数",
    "口座自然キー",
]


def write_amount_source(path: str | Path, batch, payees, invoice_counts,
                        *, encoding: str = "cp932") -> None:
    """列仕様が確定するまでの中間成果物を書き出す。

    encoding は cp932 が既定（Excelでそのまま開ける）。FB-Web が UTF-8 を
    要求するなら現場で切り替える — ONSITE.md ② で記録すること。
    """
    path = Path(path)
    with path.open("w", encoding=encoding, newline="", errors="strict") as fh:
        w = csv.writer(fh)
        w.writerow(AMOUNT_SOURCE_HEADERS)
        for p in batch.payments:
            master = payees.get(p.payee_id)
            raw1 = getattr(master, "customer_code_1", "") if master else ""
            raw2 = getattr(master, "customer_code_2", "") if master else ""
            key = account_key(p.bank_code, p.branch_code, p.deposit_type,
                              p.account_number)
            w.writerow([
                p.payee_id,
                normalize_code(raw1),
                raw1,
                normalize_code(raw2),
                p.bank_code,
                p.branch_code,
                p.deposit_type,
                p.account_number,
                p.payee_name_kana,
                p.amount,
                ("先方負担" if any(n.startswith("先方負担") for n in p.notes)
                 else "当方負担"),
                invoice_counts.get(p.payee_id, 0),
                "-".join(key),
            ])
