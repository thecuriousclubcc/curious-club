"""Bundle the package into ONE self-contained .py file.

院内へのコード搬入経路が未解決のため、依存パッケージなし・単一ファイルで
成立する形を用意する。USB1本、メール1通、最悪テキストエディタへの貼り付けでも
持ち込める。標準ライブラリ以外を一切使わないので、院内のPython 3.8+ があれば動く。

    python3 build_single_file.py  ->  dist/mirai_keiri.py
"""

from __future__ import annotations

import pathlib
import re

ORDER = ["model", "kana", "custcode", "tnumber", "fees", "reconcile",
         "history", "templates", "format", "master", "invoices", "amounts",
         "ocr", "readers", "intake", "measure", "review", "review_server", "xlsx", "sheet", "verify", "cli"]

HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mirai-keiri — 請求書 → 全銀 総合振込 / 振込一覧表（単一ファイル版）

自動生成。編集は tools/mirai-keiri/zengin/ 側で行うこと。
依存パッケージなし（Python 3.8+ 標準ライブラリのみ）。外部通信なし。

  python3 mirai_keiri.py --master payees.csv --invoices invoices.csv \\
      --config requester.json --date 2026-10-31 --out out/
  python3 mirai_keiri.py --selftest      # 内蔵テストのみ実行（入力不要）
"""
'''

SELFTEST = '''

# ---------------------------------------------------------------------------
# 内蔵セルフテスト — 現場で「そもそも正しく動くか」を入力なしで確認するため
# ---------------------------------------------------------------------------
def selftest() -> int:
    import datetime
    ok, fail = 0, []

    def check(label, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(label)

    # レコード長
    for name, table in (("ヘッダー", HEADER_FIELDS), ("データ", DATA_FIELDS),
                        ("トレーラー", TRAILER_FIELDS), ("エンド", END_FIELDS)):
        check(f"{name}レコード=120バイト", sum(f.length for f in table) == 120)

    # 半角カナ
    check("濁点は2バイト", to_zengin_kana("ガ").text == "ｶﾞ")
    check("小書きは大文字化", to_zengin_kana("キャノン").text == "ｷﾔﾉﾝ")
    check("長音とハイフンの区別", to_zengin_kana("ミラー").text == "ﾐﾗｰ")
    try:
        to_zengin_kana("株式会社")
        check("漢字は拒否", False)
    except KanaError:
        check("漢字は拒否", True)

    # 顧客コード
    check("顧客コード正規化", normalize_code("9387") == "0000009387")
    check("空欄は一致しない", not same("", ""))

    # 登録番号（T+13桁）— ネットなしで検査用数字を判定できる
    check("登録番号の検査用数字", check_digit("310001000026") == 9)
    try:
        normalize_tnumber("T9310001000025")
        check("登録番号の1桁誤りを弾く", False)
    except ValidationError:
        check("登録番号の1桁誤りを弾く", True)

    # 請求書の検算 — 裏取りが無ければ通さない
    fig = InvoiceFigures(total_billed=376772, purchases=342520, tax=34252)
    check("検算が通る", reconcile(fig).payable)
    check("裏取り無しは通さない",
          not reconcile(InvoiceFigures(total_billed=376772)).payable)
    check("1桁違いを弾く",
          not reconcile(InvoiceFigures(total_billed=376779,
                                       purchases=342520, tax=34252)).payable)

    # 2σ判定
    h = History({"P": [100000, 102000, 98000, 900000, 101000]})
    check("平均がぶれても中央値で拾う", h.assess("P", 130000).needs_review)
    check("履歴なしは必ず人へ", History().assess("X", 1).needs_review)
    check("範囲内は通す",
          not History({"P": [132000, 132000, 131500, 132500]})
          .assess("P", 132000).needs_review)

    # OCR は任意。入っていなければその旨だけ出す
    if tesseract_available():
        check("tesseract が使える", True)
    else:
        print("  注意: tesseract が見つかりません（金額は手入力になります）")

    # 組み立てと検証
    req = Requester(consignor_code="2000000000", name_kana="ｲ)ﾐﾗｲ",
                    bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                    branch_code="107", branch_name_kana="ｾｲﾘﾖｳ",
                    deposit_type="1", account_number="1234567")
    pay = Payment(payee_id="T1", bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                  branch_code="201", branch_name_kana="ﾃﾝﾓﾝｶﾝ",
                  deposit_type="1", account_number="7654321",
                  payee_name_kana="ｶ)ﾃｽﾄ", amount=123456)
    batch = TransferBatch(requester=req,
                          transfer_date=datetime.date(2026, 10, 31),
                          payments=[pay])
    raw = render(batch)
    check("ファイル長=(120+2)*4", len(raw) == (120 + 2) * 4)
    check("検証器が問題なしを返す",
          verify(raw, expected_count=1, expected_total=123456) == [])
    check("識別表示は空白（手数料フラグではない）",
          raw.split(b"\\r\\n")[1][112:113] == b" ")
    check("振込指定区分=7", raw.split(b"\\r\\n")[1][111:112] == b"7")

    # 桁あふれは止まること
    try:
        build_data(Payment(payee_id="T2", bank_code="0185",
                           bank_name_kana="ｶ", branch_code="201",
                           branch_name_kana="ﾃ", deposit_type="1",
                           account_number="1", payee_name_kana="ｱ" * 31,
                           amount=1))
        check("受取人名31文字は拒否", False)
    except ValidationError:
        check("受取人名31文字は拒否", True)

    print(f"セルフテスト: {ok} 件成功, {len(fail)} 件失敗")
    for f in fail:
        print(f"  失敗: {f}")
    if not fail:
        print("→ このファイルは正しく動作しています。")
    return 0 if not fail else 1
'''


def _check_coverage() -> None:
    """パッケージの全モジュールが ORDER に入っていること。

    漏れると、そのモジュールの関数が単一ファイル版で未定義になる。
    実際に tnumber.py の漏れで NameError を出したので、機械検査にした。
    """
    on_disk = {p.stem for p in pathlib.Path("zengin").glob("*.py")
               if p.stem != "__init__"}
    missing = on_disk - set(ORDER)
    extra = set(ORDER) - on_disk
    if missing or extra:
        raise SystemExit(
            f"ORDER がパッケージと一致しません。\n"
            f"  ORDER に無い: {sorted(missing)}\n"
            f"  存在しない: {sorted(extra)}")


def _check_collisions() -> None:
    """Bundling flattens every module into one namespace.

    A name defined in two modules would silently shadow the earlier one, and
    the failure is quiet - a wrong constant, not a crash. Refuse to bundle.
    """
    import ast
    from collections import defaultdict

    owners = defaultdict(list)
    for mod in ORDER:
        tree = ast.parse((pathlib.Path("zengin") / f"{mod}.py").read_text("utf-8"))
        for node in tree.body:
            names = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            for n in names:
                # アンダースコア始まりも平坦化すれば衝突する。除外しない。
                if not n.startswith("__"):
                    owners[n].append(mod)

    clashes = {n: m for n, m in owners.items() if len(m) > 1}
    if clashes:
        lines = "\n".join(f"  {n}: {', '.join(m)}" for n, m in sorted(clashes.items()))
        raise SystemExit(
            f"名前の衝突があります。単一ファイル化すると先に定義した方が\n"
            f"静かに上書きされます。改名してください:\n{lines}")


def bundle() -> str:
    _check_coverage()
    _check_collisions()
    parts = [HEADER]
    seen_imports = set()
    bodies = []

    for mod in ORDER:
        src = pathlib.Path("zengin") / f"{mod}.py"
        text = src.read_text(encoding="utf-8")
        # Strip each module's own __main__ block; the bundle supplies one.
        text = re.split(r'\nif __name__ == "__main__":', text)[0]
        lines = []
        for line in text.split("\n"):
            # Drop intra-package imports; everything lands in one namespace.
            if re.match(r"\s*from \.\w* import", line) or re.match(r"\s*from \. import", line):
                continue
            if re.match(r"\s*from __future__ import", line):
                seen_imports.add("from __future__ import annotations")
                continue
            m = re.match(r"^(import \S+|from [\w.]+ import .+)$", line)
            if m and not line.startswith("from ."):
                seen_imports.add(line)
                continue
            lines.append(line)
        bodies.append(f"\n# ===== {mod}.py " + "=" * (60 - len(mod)) + "\n"
                      + "\n".join(lines))

    parts.append("from __future__ import annotations\n")
    for imp in sorted(i for i in seen_imports if "__future__" not in i):
        parts.append(imp)
    parts.append("\n")
    parts.extend(bodies)
    parts.append(SELFTEST)
    parts.append('''

if __name__ == "__main__":
    import sys as _sys
    if "--selftest" in _sys.argv:
        raise SystemExit(selftest())
    if "--review" in _sys.argv:
        _sys.argv.remove("--review")
        print("確認画面を出すには、パイプラインから ReviewQueue を渡します。")
        print("単体では確認待ちが無いため、何も表示されません。")
        raise SystemExit(0)
    if "--measure" in _sys.argv:
        _sys.argv.remove("--measure")
        raise SystemExit(measure_main())
    raise SystemExit(main())
''')
    return "\n".join(parts)


if __name__ == "__main__":
    out = pathlib.Path("dist"); out.mkdir(exist_ok=True)
    target = out / "mirai_keiri.py"
    target.write_text(bundle(), encoding="utf-8")
    print(f"{target} ({target.stat().st_size:,} bytes, "
          f"{len(bundle().splitlines()):,} lines)")
