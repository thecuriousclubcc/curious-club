"""顧客コード (FB-Web 受取人マスタのコード1/コード2) の正規化.

実データでは 10桁ゼロ埋め (`0000000010`) と 4桁そのまま (`9387`) が混在する。
素の文字列比較では同一先が別物になるため、突合前に必ず正規化する。

数値化 (int) による比較は採らない: 先頭ゼロが落ち、桁数の情報も失われる。
固定幅のゼロ埋め文字列のまま扱う。
"""

from __future__ import annotations

from .model import ValidationError

WIDTH = 10


def normalize_code(code: str | None, *, width: int = WIDTH) -> str:
    """'9387' -> '0000009387'. 空欄は空文字のまま返す（照合不能の印）。"""
    if code is None:
        return ""
    s = str(code).strip()
    if not s:
        return ""
    if not s.isdigit():
        raise ValidationError(f"顧客コードが数字ではありません: {code!r}")
    if len(s) > width:
        raise ValidationError(f"顧客コードが{width}桁を超えています: {code!r}")
    return s.zfill(width)


def same(a: str | None, b: str | None) -> bool:
    """両方に値があり、正規化後に一致したときだけ True。空欄は一致扱いしない。"""
    na, nb = normalize_code(a), normalize_code(b)
    return bool(na) and na == nb


def account_key(bank_code: str, branch_code: str, deposit_type: str,
                account_number: str) -> tuple[str, str, str, str]:
    """口座の自然キー。顧客コードが未整備の先でも必ず引ける（案A）。"""
    return (bank_code.strip().zfill(4), branch_code.strip().zfill(3),
            deposit_type.strip(), account_number.strip().zfill(7))
