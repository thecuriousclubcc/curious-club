"""CLI: 請求書明細 + 振込先マスタ -> 振込一覧表(.xlsx) + 全銀ファイル(.txt).

    python3 -m zengin.cli \
        --master   data/payees.csv \
        --invoices data/invoices-2026-10.csv \
        --config   data/requester.json \
        --date     2026-10-31 \
        --out      out/

The 全銀 file is written only after the independent verifier passes. The file
is never transmitted by this tool: a human uploads it to FB-Web.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .format import render
from .invoices import aggregate, detect_anomalies, load_invoices
from .master import load_payees
from .model import Requester, TransferBatch, ValidationError
from .sheet import write_review_sheet
from .verify import verify


def load_history(path: Path | None) -> dict[str, list[int]]:
    if not path or not path.exists():
        return {}
    return {k: [int(x) for x in v] for k, v in json.loads(path.read_text()).items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="全銀 総合振込ファイル生成")
    ap.add_argument("--master", required=True, help="振込先マスタ CSV")
    ap.add_argument("--invoices", required=True, help="請求書明細 CSV")
    ap.add_argument("--config", required=True, help="委託者情報 JSON")
    ap.add_argument("--date", required=True, help="取組日 YYYY-MM-DD")
    ap.add_argument("--out", required=True, help="出力ディレクトリ")
    ap.add_argument("--history", help="支払履歴 JSON (2σ判定用)")
    ap.add_argument("--newline", default="crlf", choices=["crlf", "none"])
    ap.add_argument("--route", default="zengin", choices=["zengin", "screen"],
                    help="zengin=外部ファイル送信 / screen=データ登録(金額外部取込)")
    ap.add_argument("--fees", help="手数料テーブル JSON (先方負担がある場合に必須)")
    ap.add_argument("--emit-amounts", action="store_true",
                    help="金額取込用CSVの素材を出力（列仕様確定前の中間成果物）")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="口座未確認の支払先を許可（通常は使わない）")
    args = ap.parse_args(argv)

    try:
        transfer_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"エラー: --date は YYYY-MM-DD 形式です: {args.date}", file=sys.stderr)
        return 2

    try:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        requester = Requester(**cfg)
        payees = load_payees(args.master)
        invoices = load_invoices(args.invoices)
        from .fees import FeePolicy, Route
        fee_policy = None
        if args.fees:
            fee_policy = FeePolicy(**json.loads(
                Path(args.fees).read_text(encoding="utf-8")))
        payments = aggregate(invoices, payees,
                             require_verified=not args.allow_unverified,
                             route=Route(args.route), fee_policy=fee_policy)
        batch = TransferBatch(requester=requester, transfer_date=transfer_date,
                              payments=payments)
        batch.validate()
    except ValidationError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, TypeError) as e:
        print(f"エラー: 設定または入力が読めません: {e}", file=sys.stderr)
        return 1

    anomalies = detect_anomalies(invoices, load_history(
        Path(args.history) if args.history else None))

    newline = "\r\n" if args.newline == "crlf" else ""
    raw = render(batch, newline=newline)

    problems = verify(raw, expected_count=batch.total_count,
                      expected_total=batch.total_amount)
    if problems:
        print("検証に失敗しました。ファイルは出力していません:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = transfer_date.strftime("%Y%m%d")
    zengin_path = out_dir / f"sougou_furikomi_{stamp}.txt"
    sheet_path = out_dir / f"振込一覧表_{stamp}.xlsx"

    zengin_path.write_bytes(raw)
    write_review_sheet(str(sheet_path), batch, invoices, anomalies)

    if args.emit_amounts:
        from .amounts import write_amount_source
        counts: dict[str, int] = {}
        for r in invoices:
            counts[r.payee_id] = counts.get(r.payee_id, 0) + 1
        amounts_path = out_dir / f"金額取込素材_{stamp}.csv"
        write_amount_source(amounts_path, batch, payees, counts)
        print(f"金額取込素材: {amounts_path}  ※列仕様は現場で確定させること")

    print(f"振込一覧表: {sheet_path}")
    print(f"全銀ファイル: {zengin_path} ({len(raw)} バイト)")
    print(f"件数: {batch.total_count}  合計: {batch.total_amount:,} 円")
    if anomalies:
        print(f"\n確認事項 {len(anomalies)} 件（承認前に確認してください）:")
        for a in anomalies:
            print(f"  - {a.payee_id}: {a.message}")
    print("\n次の手順: 振込一覧表を承認者が確認・押印 → FB-Web に全銀ファイルを送信。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
