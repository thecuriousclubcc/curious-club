"""院内へ運ぶ一式を組み立てる（USB不可・共有フォルダ経由）。

想定する経路:
    ネットにつながる端末（右PC）
        → pip download で wheel を集める
        → 本スクリプトで 1つのフォルダにまとめ、SHA-256 の一覧を作る
        → 新共有 にコピー
    閉じた端末（左PC）
        → 新共有 から取り出す
        → verify_transfer.py でハッシュを照合（壊れ・取り違えを検出）
        → 照合が通ってから install

共有フォルダ越しのコピーは、途中で切れても「それらしいファイル」が残る。
実行コードを運ぶので、**入れる前に必ず照合する**。照合は左PCだけで完結し、
ネットに出ない（hashlib のみ）。

    python3 make_transfer_bundle.py --wheels offline --out 搬入_20260926
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import sys
from datetime import date
from pathlib import Path

MANIFEST = "MANIFEST.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(wheels: Path | None, out: Path, *, note: str = "") -> None:
    out.mkdir(parents=True, exist_ok=True)

    here = Path(__file__).resolve().parent
    single = here / "dist" / "mirai_keiri.py"
    if not single.exists():
        raise SystemExit(
            f"{single} がありません。先に python3 build_single_file.py を実行してください。")
    shutil.copy2(single, out / "mirai_keiri.py")
    shutil.copy2(here / "verify_transfer.py", out / "verify_transfer.py")

    n_wheels = 0
    if wheels:
        if not wheels.is_dir():
            raise SystemExit(f"{wheels} がありません。")
        dest = out / "offline"
        dest.mkdir(exist_ok=True)
        for w in sorted(wheels.glob("*")):
            if w.is_file():
                shutil.copy2(w, dest / w.name)
                n_wheels += 1

    files = sorted(p for p in out.rglob("*")
                   if p.is_file() and p.name != MANIFEST)
    lines = [f"{sha256(p)}  {p.relative_to(out).as_posix()}" for p in files]
    total = sum(p.stat().st_size for p in files)
    (out / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = out / "はじめにお読みください.txt"
    readme.write_text(f"""mirai-keiri 搬入一式
作成日: {date.today()}
作成した端末: {platform.system()} / Python {sys.version.split()[0]}
{note}

■ 左PC（閉じた端末）での手順

1. このフォルダごと 新共有 から取り出す

2. 中身が壊れていないか確かめる（必ず最初に）
       python3 verify_transfer.py

   「すべて一致しました」と出るまで先へ進まないこと。
   1つでも不一致なら、コピーし直す。

3. 動くか確かめる（入力ファイル不要）
       python3 mirai_keiri.py --selftest

   「0 件失敗」と出ればOK。

4. OCRを使う場合のみ（任意）
       pip install --no-index --find-links offline rapidocr-onnxruntime

   ※ offline フォルダの wheel は、この端末の OS と Python の版に
     合っていないと入らない。合わない場合は右PCで
         pip download --dest offline --platform <左PCの環境> \\
             --python-version <左PCの版> --only-binary=:all: \\
             rapidocr-onnxruntime
     をやり直すこと。

■ 含まれるもの
   mirai_keiri.py       本体（単一ファイル・依存なし）
   verify_transfer.py   照合スクリプト
   offline/             OCR用 wheel（{n_wheels} 個）
   {MANIFEST}           SHA-256 の一覧

   ファイル数 {len(files)} / 合計 {total / 1024 / 1024:.1f} MB
""", encoding="utf-8")

    # README を足したので一覧を作り直す
    files = sorted(p for p in out.rglob("*")
                   if p.is_file() and p.name != MANIFEST)
    (out / MANIFEST).write_text(
        "\n".join(f"{sha256(p)}  {p.relative_to(out).as_posix()}"
                  for p in files) + "\n", encoding="utf-8")

    print(f"{out}/ を作成しました")
    print(f"  ファイル {len(files)} 個 / "
          f"{sum(p.stat().st_size for p in files) / 1024 / 1024:.1f} MB"
          f"（うち wheel {n_wheels} 個）")
    print(f"  このフォルダごと 新共有 にコピーしてください。")
    print(f"  左PCでは必ず先に  python3 verify_transfer.py  を実行。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="院内搬入一式を作る")
    ap.add_argument("--wheels", type=Path,
                    help="pip download で集めた wheel のフォルダ（省略可）")
    ap.add_argument("--out", type=Path, required=True, help="出力先フォルダ")
    ap.add_argument("--note", default="", help="README に書き添える一行")
    a = ap.parse_args()
    build(a.wheels, a.out, note=a.note)
