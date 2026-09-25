"""適格請求書発行事業者登録番号（T + 法人番号13桁）の取り扱い。

用途は**取引先マスタの照合キー**。国税庁への問い合わせは行わない。
院内は閉鎖環境でネットに出られないし、取引先は概ね固定で新規は稀なので、
自前のマスタに登録しておけば完全一致で引ける。

ただし1つ強い性質がある: 法人番号には検査用数字（チェックディジット）が
先頭1桁に入っているため、**ネットなしで番号の妥当性を判定できる**。
OCRが1桁読み違えた番号は、照合する前にここで弾ける。

  検査用数字 = 9 −( Σ(n=1..12) Pn × Qn ) mod 9
    Pn: 法人番号の下12桁を最下位から数えた n 桁目の数字
    Qn: n が奇数なら 1、偶数なら 2
  （国税庁 法人番号システム 仕様）
"""

from __future__ import annotations

import re

from .model import ValidationError

PATTERN = re.compile(r"^T?(\d{13})$")


def check_digit(body12: str) -> int:
    """下12桁から検査用数字を計算する。"""
    total = 0
    for n, ch in enumerate(reversed(body12), start=1):
        total += int(ch) * (1 if n % 2 else 2)
    return 9 - (total % 9)


def is_valid(number: str) -> bool:
    """T番号として整合しているか。ネットアクセスなしで判定する。"""
    try:
        normalize_tnumber(number)
        return True
    except ValidationError:
        return False


def normalize_tnumber(number: str) -> str:
    """'t9310001000026' や全角混じりを 'T9310001000026' に整える。

    桁数・数字・検査用数字のいずれかが合わなければ例外。
    読み取り誤りを黙って通さない。
    """
    if number is None:
        raise ValidationError("登録番号が空です")

    s = str(number).strip().upper()
    # 全角→半角、区切り記号の除去
    s = s.translate(str.maketrans(
        "０１２３４５６７８９Ｔ", "0123456789T"))
    s = s.replace("-", "").replace("‐", "").replace("－", "")
    s = s.replace(" ", "").replace("　", "")

    m = PATTERN.match(s)
    if not m:
        raise ValidationError(
            f"登録番号の形式が不正です（T＋13桁の数字）: {number!r}")

    digits = m.group(1)
    want = check_digit(digits[1:])
    got = int(digits[0])
    if got != want:
        raise ValidationError(
            f"登録番号の検査用数字が合いません: {number!r} "
            f"(先頭 {got} / 計算 {want})。読み取り誤りの可能性があります。")
    return "T" + digits


def match(read_number: str, master: dict[str, str]) -> str | None:
    """読み取った登録番号から payee_id を引く。完全一致のみ。

    master: {正規化済みT番号: payee_id}
    見つからなければ None を返す（＝新規取引先。人に回す）。
    推測による部分一致は行わない。
    """
    try:
        key = normalize_tnumber(read_number)
    except ValidationError:
        return None
    return master.get(key)
