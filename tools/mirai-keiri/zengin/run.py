"""請求書PDFのフォルダを1コマンドで処理する。

    python3 mirai_keiri.py --process \
        --pdfs 新共有/請求書/2026-10 \
        --templates data/templates/invoice_templates.json \
        --master data/payees.csv \
        --config data/requester.json \
        --date 2026-10-31 \
        --out out/

確認待ちが残れば、銀行用ファイルは作らずに確認画面を出す。
確認が済んでからもう一度実行すれば、出力まで進む。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .fees import FeePolicy, Route
from .format import render
from .history import History
from .master import load_payees
from .model import Requester, TransferBatch, ValidationError
from .pipeline import process, to_payments
from .sheet import write_review_sheet
from .templates import load_templates
from .verify import verify


def _pdfs(folder: str | Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir()
                  if p.suffix.lower() == ".pdf")


def run_main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="請求書PDFのフォルダから振込一覧表と銀行用ファイルを作る")
    ap.add_argument("--pdfs", required=True, help="請求書PDFのフォルダ")
    ap.add_argument("--templates", required=True)
    ap.add_argument("--master", required=True, help="振込先マスタ CSV")
    ap.add_argument("--config", required=True, help="委託者情報 JSON")
    ap.add_argument("--date", required=True, help="取組日 YYYY-MM-DD")
    ap.add_argument("--out", required=True)
    ap.add_argument("--history", help="支払履歴 JSON（2σ判定に使う）")
    ap.add_argument("--fees", help="手数料テーブル JSON")
    ap.add_argument("--route", default="zengin", choices=["zengin", "screen"])
    ap.add_argument("--preset", default="rapidocr")
    ap.add_argument("--work", default="work", help="ページ画像の作業場所")
    ap.add_argument("--serve", action="store_true",
                    help="確認待ちがあれば確認画面を立ち上げる")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)

    try:
        transfer_date = datetime.strptime(a.date, "%Y-%m-%d").date()
        requester = Requester(**json.loads(
            Path(a.config).read_text(encoding="utf-8")))
        templates = load_templates(a.templates)
        payees = load_payees(a.master)
        history = (History.load(a.history) if a.history else History())
    except ValidationError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"エラー: 設定が読めません: {e}", file=sys.stderr)
        return 1

    pdfs = _pdfs(a.pdfs)
    if not pdfs:
        print(f"エラー: {a.pdfs} に PDF がありません", file=sys.stderr)
        return 1

    print(f"請求書PDF {len(pdfs)}件 を読みます（1ページ数秒かかります）…\n")
    try:
        result = process(pdfs, templates=templates, payees=payees,
                         history=history, work_dir=a.work, preset=a.preset)
    except ValidationError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    for line in result.lines():
        print(line)

    if not result.can_output:
        print("\n── 確認が必要なもの ──")
        for it in result.queue.pending():
            print(f"  ・{it.display_name}: {it.reason}")
            if it.detail:
                print(f"      {it.detail[:100]}")
        if a.serve:
            from .review_server import serve
            srv = serve(result.queue, a.port)
            print("\n確認が終わったら Ctrl+C で止めて、もう一度実行してください。")
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                print("\n確認画面を閉じました。")
        else:
            print("\n確認画面を出すには --serve を付けて実行してください。")
        return 2

    # ここから先は確認待ちが無い場合だけ
    try:
        payments = to_payments(result, payees)
        fee_policy = (FeePolicy(**json.loads(
            Path(a.fees).read_text(encoding="utf-8"))) if a.fees else None)
        for p in payments:
            master = payees[p.payee_id]
            if master.fee_borne_by == "beneficiary":
                from .fees import resolve_amount
                p.amount, fee = resolve_amount(
                    p.amount, fee_borne_by="beneficiary",
                    route=Route(a.route), policy=fee_policy,
                    bank_code=p.bank_code, branch_code=p.branch_code)
                if fee:
                    p.notes.append(f"先方負担: 手数料 {fee:,}円 を差引き")
        batch = TransferBatch(requester=requester,
                              transfer_date=transfer_date, payments=payments)
        batch.validate()
        raw = render(batch)
    except ValidationError as e:
        print(f"\nエラー: {e}", file=sys.stderr)
        return 1

    problems = verify(raw, expected_count=batch.total_count,
                      expected_total=batch.total_amount)
    if problems:
        print("\n検証に失敗しました。ファイルは出力していません:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = transfer_date.strftime("%Y%m%d")
    (out / f"sougou_furikomi_{stamp}.txt").write_bytes(raw)
    write_review_sheet(str(out / f"振込一覧表_{stamp}.xlsx"), batch, [], [])
    if result.queue.overrides:
        result.queue.save_overrides(out / f"手入力の記録_{stamp}.json")

    print(f"\n振込一覧表: {out / f'振込一覧表_{stamp}.xlsx'}")
    print(f"銀行用ファイル: {out / f'sougou_furikomi_{stamp}.txt'} "
          f"({len(raw)} バイト)")
    print(f"件数: {batch.total_count}  合計: {batch.total_amount:,} 円")
    print("\n次の手順: 振込一覧表を承認者が確認・押印 → FB-Web に送信。")
    return 0
