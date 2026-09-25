"""搬入した一式が壊れていないか照合する（左PCで実行）。

共有フォルダ越しのコピーは、途中で切れても「それらしいファイル」が残る。
実行コードを入れる前に、SHA-256 で1件ずつ突き合わせる。

ネットには出ない。標準ライブラリの hashlib のみを使う。

    python3 verify_transfer.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

MANIFEST = "MANIFEST.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(root: Path | None = None) -> int:
    root = root or Path(__file__).resolve().parent
    manifest = root / MANIFEST
    if not manifest.exists():
        print(f"エラー: {MANIFEST} がありません。一式が揃っていません。")
        return 2

    expected: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        expected[name] = digest

    ok = missing = bad = 0
    for name, want in sorted(expected.items()):
        p = root / name
        if not p.exists():
            print(f"  ✗ 見つかりません: {name}")
            missing += 1
            continue
        got = sha256(p)
        if got != want:
            print(f"  ✗ 中身が違います: {name}")
            print(f"      期待 {want[:16]}… / 実際 {got[:16]}…")
            bad += 1
        else:
            ok += 1

    extra = [p for p in root.rglob("*")
             if p.is_file() and p.name != MANIFEST
             and p.relative_to(root).as_posix() not in expected]
    for p in extra:
        print(f"  ! 一覧にないファイル: {p.relative_to(root).as_posix()}")

    print()
    if missing or bad:
        print(f"照合に失敗しました（一致 {ok} / 不一致 {bad} / 欠落 {missing}）")
        print("新共有 からコピーし直してください。install しないこと。")
        return 1

    print(f"すべて一致しました（{ok} 件）。")
    if extra:
        print(f"※ 一覧にないファイルが {len(extra)} 個あります。心当たりが")
        print("   なければ、コピー元を確認してください。")
    print("次: python3 mirai_keiri.py --selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
