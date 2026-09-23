"""Bundle the package into ONE self-contained .py file.

院内へのコード搬入経路が未解決のため、依存パッケージなし・単一ファイルで
成立する形を用意する。USB1本、メール1通、最悪テキストエディタへの貼り付けでも
持ち込める。標準ライブラリ以外を一切使わないので、院内のPython 3.8+ があれば動く。

    python3 build_single_file.py  ->  dist/mirai_keiri.py
"""

from __future__ import annotations

import pathlib
import re

ORDER = ["model", "kana", "custcode", "fees", "format", "master",
         "invoices", "xlsx", "sheet", "verify", "cli"]

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
    check("顧客コード正規化", normalize("9387") == "0000009387")
    check("空欄は一致しない", not same("", ""))

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
                if not n.startswith("_"):
                    owners[n].append(mod)

    clashes = {n: m for n, m in owners.items() if len(m) > 1}
    if clashes:
        lines = "\n".join(f"  {n}: {', '.join(m)}" for n, m in sorted(clashes.items()))
        raise SystemExit(
            f"名前の衝突があります。単一ファイル化すると先に定義した方が\n"
            f"静かに上書きされます。改名してください:\n{lines}")


def bundle() -> str:
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
    raise SystemExit(main())
''')
    return "\n".join(parts)


if __name__ == "__main__":
    out = pathlib.Path("dist"); out.mkdir(exist_ok=True)
    target = out / "mirai_keiri.py"
    target.write_text(bundle(), encoding="utf-8")
    print(f"{target} ({target.stat().st_size:,} bytes, "
          f"{len(bundle().splitlines()):,} lines)")
