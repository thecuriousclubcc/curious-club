#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mirai-keiri — 請求書 → 全銀 総合振込 / 振込一覧表（単一ファイル版）

自動生成。編集は tools/mirai-keiri/zengin/ 側で行うこと。
依存パッケージなし（Python 3.8+ 標準ライブラリのみ）。外部通信なし。

  python3 mirai_keiri.py --master payees.csv --invoices invoices.csv \
      --config requester.json --date 2026-10-31 --out out/
  python3 mirai_keiri.py --selftest      # 内蔵テストのみ実行（入力不要）
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from dataclasses import dataclass, field
from datetime import date
from datetime import date, datetime
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Protocol
from xml.sax.saxutils import escape
import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import zipfile



# ===== model.py =======================================================
"""Data model for a 総合振込 (general transfer) run.

Amounts are integer yen everywhere. Floats are never used: a float cent-error
on a bank transfer is unrecoverable once the file is accepted.
"""



# 預金種目 (deposit type) codes, per 全銀協規定形式.
DEPOSIT_TYPES = {
    "1": "普通",
    "2": "当座",
    "4": "貯蓄",
    "9": "その他",
}

# 新規コード (record status).
NEW_CODES = {
    "0": "その他",
    "1": "第1回",
    "2": "変更",
}

# 振込指定区分.
TRANSFER_KINDS = {
    "7": "テレ振込",
    "8": "文書振込",
    " ": "指定なし",
}

# 識別表示 (data record byte 113).
#   "Y"   = EDI情報を使用する。このとき項番12・13（顧客コード1・2, bytes
#           92-111）は 20桁の EDI情報として再解釈される。
#   space = EDI情報を使用しない。項番12・13は顧客コードのまま。
# 手数料負担先はこの項目ではない。全銀フォーマットに振込手数料の項目は
# 存在せず、先方負担はアップロード画面側で指定し、ファイル内の全明細に
# 一括適用される（FB-Web 外部ファイル送信も同様）。
EDI_IN_USE = "Y"
EDI_NOT_USED = " "


class ValidationError(ValueError):
    """Raised when data cannot produce a byte-correct Zengin file."""


@dataclass(frozen=True)
class Requester:
    """委託者 - the clinic, as registered with 鹿児島銀行."""

    consignor_code: str      # 委託者コード (10) - issued by the bank
    name_kana: str           # 委託者名 (40)
    bank_code: str           # 仕向銀行番号 (4)  e.g. "0185"
    bank_name_kana: str      # 仕向銀行名 (15)
    branch_code: str         # 仕向支店番号 (3)
    branch_name_kana: str    # 仕向支店名 (15)
    deposit_type: str        # 預金種目 (1)
    account_number: str      # 口座番号 (7)

    def validate(self) -> None:
        if not self.consignor_code.isdigit() or len(self.consignor_code) > 10:
            raise ValidationError(f"委託者コードが不正: {self.consignor_code!r}")
        if not (self.bank_code.isdigit() and len(self.bank_code) == 4):
            raise ValidationError(f"仕向銀行番号は4桁の数字: {self.bank_code!r}")
        if not (self.branch_code.isdigit() and len(self.branch_code) == 3):
            raise ValidationError(f"仕向支店番号は3桁の数字: {self.branch_code!r}")
        if self.deposit_type not in DEPOSIT_TYPES:
            raise ValidationError(f"預金種目が不正: {self.deposit_type!r}")
        if not self.account_number.isdigit() or len(self.account_number) > 7:
            raise ValidationError(f"口座番号が不正: {self.account_number!r}")


@dataclass
class Payment:
    """One データレコード - one transfer to one stakeholder."""

    payee_id: str                 # internal master key, not written to the file
    bank_code: str                # 被仕向銀行番号 (4)
    bank_name_kana: str           # 被仕向銀行名 (15)
    branch_code: str              # 被仕向支店番号 (3)
    branch_name_kana: str         # 被仕向支店名 (15)
    deposit_type: str             # 預金種目 (1)
    account_number: str           # 口座番号 (7)
    payee_name_kana: str          # 受取人名 (30)
    amount: int                   # 振込金額 (10) - integer yen
    new_code: str = "0"           # 新規コード (1)
    customer_code_1: str = ""     # 顧客コード1 (10)
    customer_code_2: str = ""     # 顧客コード2 (10)
    transfer_kind: str = "7"      # 振込指定区分 (1) 7=電信振込（実績値）
    edi_info: str = ""            # 識別表示="Y" のとき 顧客コード欄に入る20桁

    # Provenance - carried into the review sheet, never into the bank file.
    payee_name_display: str = ""
    source_documents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not (self.bank_code.isdigit() and len(self.bank_code) == 4):
            raise ValidationError(
                f"{self.payee_id}: 被仕向銀行番号は4桁の数字: {self.bank_code!r}")
        if not (self.branch_code.isdigit() and len(self.branch_code) == 3):
            raise ValidationError(
                f"{self.payee_id}: 被仕向支店番号は3桁の数字: {self.branch_code!r}")
        if self.deposit_type not in DEPOSIT_TYPES:
            raise ValidationError(
                f"{self.payee_id}: 預金種目が不正: {self.deposit_type!r}")
        if not self.account_number.isdigit() or not (1 <= len(self.account_number) <= 7):
            raise ValidationError(
                f"{self.payee_id}: 口座番号が不正: {self.account_number!r}")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise ValidationError(
                f"{self.payee_id}: 振込金額は整数でなければなりません: {self.amount!r}")
        if self.amount <= 0:
            raise ValidationError(
                f"{self.payee_id}: 振込金額は1円以上: {self.amount}")
        if self.amount > 9_999_999_999:
            raise ValidationError(
                f"{self.payee_id}: 振込金額が10桁を超えています: {self.amount}")
        if self.new_code not in NEW_CODES:
            raise ValidationError(
                f"{self.payee_id}: 新規コードが不正: {self.new_code!r}")
        if self.transfer_kind not in TRANSFER_KINDS:
            raise ValidationError(
                f"{self.payee_id}: 振込指定区分が不正: {self.transfer_kind!r}")
        if self.edi_info:
            if self.customer_code_1 or self.customer_code_2:
                raise ValidationError(
                    f"{self.payee_id}: EDI情報と顧客コードは同じ領域(92-111)を"
                    f"使うため併用できません。どちらか一方にしてください。")
            if len(self.edi_info.encode("cp932")) > 20:
                raise ValidationError(
                    f"{self.payee_id}: EDI情報が20桁を超えています: "
                    f"{self.edi_info!r}")

    @property
    def identifier(self) -> str:
        """識別表示 (byte 113)."""
        return EDI_IN_USE if self.edi_info else EDI_NOT_USED


@dataclass
class TransferBatch:
    """A whole 総合振込 file: one header, N data records, trailer, end."""

    requester: Requester
    transfer_date: date          # 取組日 - the value date at the bank
    payments: list[Payment] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.payments)

    @property
    def total_amount(self) -> int:
        return sum(p.amount for p in self.payments)

    def validate(self) -> None:
        self.requester.validate()
        if not self.payments:
            raise ValidationError("振込明細が0件です")
        if self.total_count > 999_999:
            raise ValidationError(f"件数が6桁を超えています: {self.total_count}")
        if self.total_amount > 999_999_999_999:
            raise ValidationError(f"合計金額が12桁を超えています: {self.total_amount}")
        for p in self.payments:
            p.validate()


# ===== kana.py ========================================================
"""Half-width katakana normalisation for Zengin (全銀協規定形式) name fields.

Zengin name fields accept only the JIS X 0201 half-width set: half-width
katakana, uppercase A-Z, digits, space and a small symbol set. Voiced marks
(ﾞ/ﾟ) are SEPARATE characters and each consumes one byte of the field.

Every transformation this module applies is reported back to the caller so the
human review sheet can show exactly what was changed. Nothing is silently
dropped: unmappable characters raise, they are never replaced with a guess.
"""



# Base katakana -> half-width.
_BASE = {
    "ア": "ｱ", "イ": "ｲ", "ウ": "ｳ", "エ": "ｴ", "オ": "ｵ",
    "カ": "ｶ", "キ": "ｷ", "ク": "ｸ", "ケ": "ｹ", "コ": "ｺ",
    "サ": "ｻ", "シ": "ｼ", "ス": "ｽ", "セ": "ｾ", "ソ": "ｿ",
    "タ": "ﾀ", "チ": "ﾁ", "ツ": "ﾂ", "テ": "ﾃ", "ト": "ﾄ",
    "ナ": "ﾅ", "ニ": "ﾆ", "ヌ": "ﾇ", "ネ": "ﾈ", "ノ": "ﾉ",
    "ハ": "ﾊ", "ヒ": "ﾋ", "フ": "ﾌ", "ヘ": "ﾍ", "ホ": "ﾎ",
    "マ": "ﾏ", "ミ": "ﾐ", "ム": "ﾑ", "メ": "ﾒ", "モ": "ﾓ",
    "ヤ": "ﾔ", "ユ": "ﾕ", "ヨ": "ﾖ",
    "ラ": "ﾗ", "リ": "ﾘ", "ル": "ﾙ", "レ": "ﾚ", "ロ": "ﾛ",
    "ワ": "ﾜ", "ヲ": "ｦ", "ン": "ﾝ",
}

# Voiced / semi-voiced -> base + separate mark.
_DAKUTEN = {
    "ガ": "ｶﾞ", "ギ": "ｷﾞ", "グ": "ｸﾞ", "ゲ": "ｹﾞ", "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ", "ジ": "ｼﾞ", "ズ": "ｽﾞ", "ゼ": "ｾﾞ", "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ", "ヂ": "ﾁﾞ", "ヅ": "ﾂﾞ", "デ": "ﾃﾞ", "ド": "ﾄﾞ",
    "バ": "ﾊﾞ", "ビ": "ﾋﾞ", "ブ": "ﾌﾞ", "ベ": "ﾍﾞ", "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ",
}

# Small kana -> LARGE. Zengin name fields are written in large kana
# (ｷﾔﾉﾝ, not ｷｬﾉﾝ). This is a real transformation, so it is reported.
_SMALL_TO_LARGE = {
    "ァ": "ｱ", "ィ": "ｲ", "ゥ": "ｳ", "ェ": "ｴ", "ォ": "ｵ",
    "ッ": "ﾂ", "ャ": "ﾔ", "ュ": "ﾕ", "ョ": "ﾖ", "ヮ": "ﾜ",
    "ヵ": "ｶ", "ヶ": "ｹ",
}

# Symbols permitted by the Zengin name character set.
_SYMBOLS = {
    "ー": "ｰ",   # U+30FC katakana long vowel
    "-": "-", "ー": "ｰ",
    "（": "(", "）": ")", "(": "(", ")": ")",
    "．": ".", ".": ".",
    "／": "/", "/": "/",
    "￥": "\\", "¥": "\\",
    "，": ",", ",": ",",
    "　": " ", " ": " ",
}

# Hyphen-like codepoints that are NOT the katakana long vowel.
_HYPHENS = {"‐", "‑", "‒", "–", "—", "―",
            "－", "﹣", "−", "・"}

_ALLOWED_SYMBOLS = set(" ().-/\\,")

# Half-width katakana already in the target set: ｦ (FF66) and ｰ..ﾟ (FF70-FF9F).
# FF61-FF65 (｡｢｣､･) are excluded - Zengin name fields do not permit them.
_HALFWIDTH_KANA = {chr(0xFF66)} | {chr(c) for c in range(0xFF70, 0xFFA0)}

# Small half-width kana (FF67-FF6F) must also be folded to large forms.
_HALFWIDTH_SMALL_TO_LARGE = {
    "ｧ": "ｱ", "ｨ": "ｲ", "ｩ": "ｳ", "ｪ": "ｴ", "ｫ": "ｵ",
    "ｬ": "ﾔ", "ｭ": "ﾕ", "ｮ": "ﾖ", "ｯ": "ﾂ",
}


@dataclass
class KanaResult:
    """Outcome of a conversion, including every change made."""

    text: str
    original: str
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.notes)


class KanaError(ValueError):
    """Raised when a character cannot be represented in the Zengin set."""


def _hiragana_to_katakana(ch: str) -> str:
    o = ord(ch)
    if 0x3041 <= o <= 0x3096:
        return chr(o + 0x60)
    return ch


def to_zengin_kana(text: str, *, allow_hiragana: bool = True) -> KanaResult:
    """Convert `text` to the Zengin half-width character set.

    Raises KanaError on any character that has no defined mapping, rather than
    guessing. A wrong payee name costs a 組戻し fee and a delayed payment, so
    an explicit failure is always preferable to a silent substitution.
    """
    out: list[str] = []
    notes: list[str] = []
    saw_small = False
    saw_hiragana = False
    saw_lower = False

    for ch in text:
        if ch in _HYPHENS:
            out.append("-")
            notes.append(f"記号 {ch!r} を '-' に正規化")
            continue

        kata = _hiragana_to_katakana(ch)
        if kata != ch:
            saw_hiragana = True
            if not allow_hiragana:
                raise KanaError(f"ひらがな {ch!r} は許可されていません: {text!r}")
            ch = kata

        if ch in _SMALL_TO_LARGE:
            saw_small = True
            out.append(_SMALL_TO_LARGE[ch])
            continue
        if ch in _HALFWIDTH_SMALL_TO_LARGE:
            saw_small = True
            out.append(_HALFWIDTH_SMALL_TO_LARGE[ch])
            continue
        if ch in _DAKUTEN:
            out.append(_DAKUTEN[ch])
            continue
        if ch in _BASE:
            out.append(_BASE[ch])
            continue
        if ch in _SYMBOLS:
            out.append(_SYMBOLS[ch])
            continue
        if ch in _HALFWIDTH_KANA:
            out.append(ch)
            continue

        # Full-width alphanumerics -> half-width.
        o = ord(ch)
        if 0xFF10 <= o <= 0xFF19:        # ０-９
            out.append(chr(o - 0xFEE0))
            continue
        if 0xFF21 <= o <= 0xFF3A:        # Ａ-Ｚ
            out.append(chr(o - 0xFEE0))
            continue
        if 0xFF41 <= o <= 0xFF5A:        # ａ-ｚ
            saw_lower = True
            out.append(chr(o - 0xFEE0 - 0x20))
            continue
        if ch.isdigit() and ch.isascii():
            out.append(ch)
            continue
        if "A" <= ch <= "Z":
            out.append(ch)
            continue
        if "a" <= ch <= "z":
            saw_lower = True
            out.append(ch.upper())
            continue
        if ch in _ALLOWED_SYMBOLS:
            out.append(ch)
            continue

        raise KanaError(
            f"全銀の文字セットに変換できない文字 {ch!r} (U+{o:04X}) が "
            f"{text!r} に含まれています。振込先マスタを手で修正してください。"
        )

    if saw_hiragana:
        notes.append("ひらがなをカタカナに変換")
    if saw_small:
        notes.append("小書き文字を大文字に変換（全銀の記入規則）")
    if saw_lower:
        notes.append("英小文字を大文字に変換")

    return KanaResult(text="".join(out), original=text, notes=notes)


def byte_length(text: str) -> int:
    """Length in Shift_JIS bytes. Every Zengin-legal character is 1 byte."""
    return len(text.encode("cp932"))


# ===== custcode.py ====================================================
"""顧客コード (FB-Web 受取人マスタのコード1/コード2) の正規化.

実データでは 10桁ゼロ埋め (`0000000010`) と 4桁そのまま (`9387`) が混在する。
素の文字列比較では同一先が別物になるため、突合前に必ず正規化する。

数値化 (int) による比較は採らない: 先頭ゼロが落ち、桁数の情報も失われる。
固定幅のゼロ埋め文字列のまま扱う。
"""



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


# ===== tnumber.py =====================================================
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


# ===== fees.py ========================================================
"""手数料負担先の扱い — the one place the two FB-Web routes disagree.

FB-Web offers two ways to submit a 総合振込:

  A. 総合振込 → データ登録 （画面入力 / 金額外部取込CSV）
     For a 先方負担 payee you enter the INVOICE amount and FB-Web subtracts
     the fee itself:  請求金額 10,000 - 手数料 110 = 振込金額 9,890
     (bank manual, 「2．振込金額を入力する」)

  B. 外部ファイル送受信 → 外部ファイル送信 （全銀レコードフォーマット）
     The amount in the file is taken as written. The manual warns:
     「手数料負担先を選択する項目が表示されますが、この項目は変更しないで
      ください。先方を選択すると振込金額が変更される場合があります」

So the SAME 請求金額 must be written differently depending on the route.
Feed a route-A amount into route B and every 先方負担 payee is overpaid by
exactly the fee; feed a route-B amount into route A and they are underpaid
twice over. This module makes the choice explicit and refuses to guess.
"""





class Route(str, Enum):
    """How the batch will reach the bank."""

    SCREEN = "screen"    # データ登録 (画面入力 / 金額外部取込) - FB-Web nets the fee
    ZENGIN = "zengin"    # 外部ファイル送信 (全銀) - we must net the fee ourselves


@dataclass(frozen=True)
class FeePolicy:
    """The clinic's 振込手数料 table, as contracted with 鹿児島銀行.

    Deliberately NOT given defaults. A guessed fee silently changes what a
    先方負担 payee receives, and the error is the size of the fee - small
    enough to go unnoticed for months. Fill this in from the bank's 手数料
    schedule (FB-Web top bar → 手数料) and confirm against a real 振込明細.
    """

    same_branch: int          # 同一店内
    same_bank_other_branch: int   # 当行本支店宛
    other_bank: int               # 他行宛
    our_bank_code: str = "0185"
    our_branch_code: str = "107"  # 西陵支店

    def fee_for(self, bank_code: str, branch_code: str) -> int:
        if bank_code != self.our_bank_code:
            return self.other_bank
        if branch_code == self.our_branch_code:
            return self.same_branch
        return self.same_bank_other_branch


def resolve_amount(invoice_total: int, *, fee_borne_by: str, route: Route,
                   policy: FeePolicy | None, bank_code: str,
                   branch_code: str) -> tuple[int, int]:
    """Return (amount_to_write, fee_deducted) for one payee.

    For 当方負担 the written amount is the invoice total under both routes.
    For 先方負担 the written amount depends on the route, per this module's
    docstring.
    """
    if fee_borne_by == "sender":
        return invoice_total, 0

    if fee_borne_by != "beneficiary":
        raise ValidationError(f"fee_borne_by が不正: {fee_borne_by!r}")

    if route is Route.SCREEN:
        # FB-Web subtracts the fee on its side; write the invoice amount.
        return invoice_total, 0

    # Route.ZENGIN - we must net it down ourselves.
    if policy is None:
        raise ValidationError(
            "先方負担の支払先がありますが、手数料テーブル(FeePolicy)が未設定です。"
            "全銀ファイル経路では手数料を自分で差し引く必要があります。"
            "銀行の手数料表を確認して設定してください（推測はしません）。")

    fee = policy.fee_for(bank_code, branch_code)
    net = invoice_total - fee
    if net <= 0:
        raise ValidationError(
            f"請求額 {invoice_total:,}円 から手数料 {fee:,}円 を引くと "
            f"{net:,}円 になります。先方負担の設定を確認してください。")
    return net, fee


# ===== reconcile.py ===================================================
"""請求書の自己検算。

請求書に書かれた数字は互いに整合している。読み取り手（OCR・LLM・人）が
何であっても、読んだ結果が正しいかは**計算で判定できる**。

    繰越額     = 前回御請求額 − 御入金額
    今回合計額 = 今回御買上額 + 今回消費税額
    今回御請求額 = 繰越額 + 今回合計金額
    今回消費税額 ≈ 今回御買上額 × 税率

この検算に通らない読み取りは、読み手が誰であれ採用しない。
**読み取り器は提案するだけで、合否はここが決める。**

これにより、抽出に OCR を使おうとローカルLLMを使おうと、誤った金額が
振込データに入る経路がなくなる。LLMを使う場合でも、LLMは
「どの数字がどの項目か」を提案するだけで、最終判断は持たない。
"""





@dataclass
class InvoiceFigures:
    """請求書の表から読み取った数字。すべて整数（円）。

    読み取れなかった項目は None。None の項目に関わる検算は
    「検算できない」として扱い、勝手に補完しない。
    """

    previous_billed: int | None = None    # 前回御請求額
    payment_received: int | None = None   # 御入金額
    carried_over: int | None = None       # 繰越額
    purchases: int | None = None          # 今回御買上額
    tax: int | None = None                # 今回消費税額
    subtotal: int | None = None           # 今回合計金額
    total_billed: int | None = None       # 今回御請求額  ← 実際に払う額

    source_file: str = ""
    read_by: str = ""                     # "ocr" / "llm" / "manual" など
    line_items_total: int | None = None   # 明細の金額合計（取れた場合）


@dataclass
class ReconcileResult:
    ok: bool
    checked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    corroborated: bool = False   # 支払額が検算で裏取りされたか

    @property
    def payable(self) -> bool:
        """自動で先に進めてよいか。

        不整合がないだけでは足りない。**支払額そのものが少なくとも1つの
        検算で裏取りされていること**を要求する。読み取れた項目が少ないと
        検算は「できない(skipped)」になるが、それは「合格」ではない。
        1回しか読んでいない数字をそのまま振り込むのが一番危ない。
        """
        return self.ok and not self.failures and self.corroborated


def reconcile(f: InvoiceFigures, *, tax_rate: str = "0.10",
              tax_tolerance: int = 1) -> ReconcileResult:
    """請求書内部の整合をとる。

    tax_tolerance: 消費税の端数処理（切捨/四捨五入）が業者ごとに違うため、
    ±1円までは許容する。2円以上ずれたら読み取り誤りとみなす。
    """
    checked: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []

    def check(label: str, got, want) -> None:
        if got is None or want is None:
            skipped.append(label)
            return
        checked.append(label)
        if got != want:
            failures.append(f"{label}: 記載 {got:,} ≠ 計算 {want:,} "
                            f"(差 {got - want:+,})")

    # 繰越額 = 前回御請求額 − 御入金額
    if f.previous_billed is not None and f.payment_received is not None:
        check("繰越額", f.carried_over, f.previous_billed - f.payment_received)
    else:
        skipped.append("繰越額")

    # 今回合計金額 = 今回御買上額 + 今回消費税額
    if f.purchases is not None and f.tax is not None:
        check("今回合計金額", f.subtotal, f.purchases + f.tax)
    else:
        skipped.append("今回合計金額")

    # 今回御請求額 = 繰越額 + 今回合計金額
    corroborated = False
    if f.carried_over is not None and f.subtotal is not None:
        before = len(failures)
        check("今回御請求額", f.total_billed, f.carried_over + f.subtotal)
        if f.total_billed is not None and len(failures) == before:
            corroborated = True
    else:
        skipped.append("今回御請求額")

    # 裏取りの代替経路: 繰越が読めなくても 買上+税 と一致すれば認める
    # （繰越0の請求書ではこちらが効く）
    if (not corroborated and f.total_billed is not None
            and f.purchases is not None and f.tax is not None
            and f.carried_over in (0, None)):
        if f.total_billed == f.purchases + f.tax:
            checked.append("今回御請求額(買上+税との一致)")
            corroborated = True

    # 消費税 ≈ 買上額 × 税率（端数処理の差は許容）
    if f.purchases is not None and f.tax is not None:
        expected = int(Decimal(f.purchases) * Decimal(tax_rate))
        checked.append("消費税率")
        if abs(f.tax - expected) > tax_tolerance:
            failures.append(
                f"消費税率: 記載 {f.tax:,} ≠ {f.purchases:,}×{tax_rate} "
                f"≈ {expected:,} (差 {f.tax - expected:+,})")
    else:
        skipped.append("消費税率")

    # 明細合計 = 今回御買上額
    if f.line_items_total is not None and f.purchases is not None:
        check("明細合計", f.line_items_total, f.purchases)
    else:
        skipped.append("明細合計")

    # 実際に払う額が取れていなければ、そもそも先へ進めない。
    if f.total_billed is None:
        failures.append("今回御請求額が読み取れていません")
    elif f.total_billed < 0:
        failures.append(f"今回御請求額が負です: {f.total_billed:,}")

    if f.total_billed is not None and not corroborated:
        failures.append(
            "今回御請求額を裏取りできませんでした（他の欄が読めていないため"
            "検算が成立しない）。1回しか読めていない金額は採用しません。")

    return ReconcileResult(ok=not failures, checked=checked, skipped=skipped,
                           failures=failures, corroborated=corroborated)


def accept_or_raise(f: InvoiceFigures, **kw) -> int:
    """検算に通れば支払額を返す。通らなければ止める。

    読み取り器が OCR でもLLMでも人でも、通る条件は同じ。
    読み手を信用するのではなく、数字の整合を信用する。
    """
    r = reconcile(f, **kw)
    if not r.payable:
        detail = "; ".join(r.failures)
        raise ValidationError(
            f"{f.source_file or '請求書'}: 検算が合いません（読み取り={f.read_by or '不明'}）"
            f" — {detail}。人が確認してください。")
    return f.total_billed  # type: ignore[return-value]


# ===== history.py =====================================================
"""支払履歴にもとづく異常検知（2σ）。

目的は「読み取りが正しいか」ではなく「**いつもと違わないか**」を見ること。
検算（reconcile.py）が捕まえるのは請求書の中で辻褄が合わない誤りだけで、
請求書そのものが正しくても金額が普段と桁違い、という事態は捕まえられない。
そこを履歴で見る。

小標本での注意:
  - 平均±2σ は外れ値に弱い。過去に1回大きな支払があると σ が膨らみ、
    その後の異常を隠してしまう。そこで **中央値＋MAD** による頑健な判定も
    併走させ、**どちらかが反応したら人に回す**。
  - n<3 では統計が成り立たない。「履歴不足」として必ず人に回す。
  - 毎回同額の先（家賃・リース等）は σ=0 になる。この場合は
    「前回と違うこと自体」を異常として扱う。

判定は**止めない**。振込一覧表に印をつけて、承認者の目を向けさせるだけ。
"""



MIN_SAMPLES = 3
DEFAULT_SIGMA = 2.0
# 中央値絶対偏差を標準偏差に合わせるための定数（正規分布のとき）
MAD_TO_SIGMA = 1.4826


@dataclass
class Assessment:
    payee_id: str
    amount: int
    verdict: str                      # "ok" / "review"
    reasons: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def needs_review(self) -> bool:
        return self.verdict == "review"


class History:
    """支払先ごとの過去の支払額。

    データの出所は運用で決める（振込一覧表の印刷、会計ソフト、通帳等）。
    **総合振込送信データ一覧には金額の列が無い**ため、そこからは作れない。
    """

    def __init__(self, data: dict[str, list[int]] | None = None):
        self._data: dict[str, list[int]] = {
            k: [int(x) for x in v] for k, v in (data or {}).items()}

    @classmethod
    def load(cls, path: str | Path) -> "History":
        p = Path(path)
        if not p.exists():
            return cls({})
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def amounts(self, payee_id: str) -> list[int]:
        return list(self._data.get(payee_id, []))

    def append(self, payee_id: str, amount: int, *, keep: int = 24) -> None:
        """確定した支払を履歴に足す。直近 keep 件だけ残す。"""
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError("金額は整数（円）で渡してください")
        xs = self._data.setdefault(payee_id, [])
        xs.append(amount)
        del xs[:-keep]

    def assess(self, payee_id: str, amount: int, *,
               sigma: float = DEFAULT_SIGMA,
               min_absolute_yen: int = 0) -> Assessment:
        past = self.amounts(payee_id)
        reasons: list[str] = []
        stats: dict = {"n": len(past)}

        if not past:
            return Assessment(payee_id, amount, "review",
                              [f"初回の支払先です（{amount:,}円）"], stats)

        if len(past) < MIN_SAMPLES:
            return Assessment(
                payee_id, amount, "review",
                [f"履歴が{len(past)}件しかなく統計判定ができません"
                 f"（今回 {amount:,}円 / 過去 "
                 f"{', '.join(f'{x:,}' for x in past)}）"], stats)

        mean = statistics.fmean(past)
        median = statistics.median(past)
        sd = statistics.stdev(past)          # 標本標準偏差
        stats.update(mean=mean, median=median, sd=sd)

        diff = amount - median
        if abs(diff) < min_absolute_yen:
            return Assessment(payee_id, amount, "ok", [], stats)

        # 毎回同額だった先
        if sd == 0:
            if amount != past[-1]:
                reasons.append(
                    f"毎回同額（{past[-1]:,}円）でしたが今回 {amount:,}円 です"
                    f"（{diff:+,}円）")
            return Assessment(payee_id, amount,
                              "review" if reasons else "ok", reasons, stats)

        # 平均±2σ
        z = (amount - mean) / sd
        stats["z"] = z
        if abs(z) >= sigma:
            direction = "高い" if z > 0 else "低い"
            reasons.append(
                f"過去平均 {mean:,.0f}円（σ={sd:,.0f}）に対し今回 {amount:,}円 — "
                f"{abs(z):.1f}σ {direction}（{amount - mean:+,.0f}円）")

        # 中央値＋MAD（外れ値に強い判定）
        mad = statistics.median([abs(x - median) for x in past])
        stats["mad"] = mad
        if mad > 0:
            rz = (amount - median) / (mad * MAD_TO_SIGMA)
            stats["robust_z"] = rz
            if abs(rz) >= sigma and not reasons:
                direction = "高い" if rz > 0 else "低い"
                reasons.append(
                    f"中央値 {median:,.0f}円 から {abs(rz):.1f}σ 相当 {direction}"
                    f"（今回 {amount:,}円 / {diff:+,}円）"
                    f"— 過去の大きな支払で平均がぶれているため中央値で判定")
        elif amount != median:
            reasons.append(
                f"過去はほぼ {median:,.0f}円 で一定でしたが今回 {amount:,}円 です"
                f"（{diff:+,}円）")

        return Assessment(payee_id, amount,
                          "review" if reasons else "ok", reasons, stats)


def assess_batch(payments, history: History, **kw) -> list[Assessment]:
    """バッチ全体を判定する。ok のものも返す（件数を数えたいため）。"""
    return [history.assess(p.payee_id, p.amount, **kw) for p in payments]


# ===== templates.py ===================================================
"""業者ごとの「欄の位置」を外部ファイルで持つ。

業者が増えるたびにコードを触るのは現実的でない。請求書のレイアウトは
業者ごとに違い、しかも増えていくので、座標は JSON に出してコードから外す。

■ 解像度の違いを吸収する
スキャンの大きさは毎回同じとは限らない（DPI設定、スキャナの入替、再スキャン）。
座標をそのまま使うと、少しずれた画像で**別の場所を読んでしまう**。
読み間違いではなく「違う欄を読んだ正しい数字」になるので質が悪い。
そこで基準サイズを記録し、実画像の大きさに比例させてから使う。

■ テンプレートの当て方
請求書の登録番号（T+13桁）または payee_id で引く。**推測で当てない。**
引けなければ人に回す。新規業者は稀なので運用できる。
"""




Box = tuple[int, int, int, int]


@dataclass
class Template:
    template_id: str
    display_name: str
    reference_size: tuple[int, int]        # 座標を測ったときの画像サイズ
    fields: dict[str, Box]
    page: int = 1
    required_fields: list[str] = field(default_factory=list)
    registration_number: str = ""
    payee_id: str = ""
    verified_on: str = ""
    verified_by: str = ""

    def validate(self) -> None:
        w, h = self.reference_size
        if w <= 0 or h <= 0:
            raise ValidationError(
                f"{self.template_id}: reference_size が不正: {self.reference_size}")
        if not self.fields:
            raise ValidationError(f"{self.template_id}: fields が空です")
        for name, box in self.fields.items():
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise ValidationError(
                    f"{self.template_id}: 欄 {name!r} の座標が基準サイズ "
                    f"{w}x{h} の外にあります: {box}")
        for name in self.required_fields:
            if name not in self.fields:
                raise ValidationError(
                    f"{self.template_id}: required_fields の {name!r} が "
                    f"fields にありません")
        if self.page < 1:
            raise ValidationError(f"{self.template_id}: page は1以上")
        if not (self.registration_number or self.payee_id):
            raise ValidationError(
                f"{self.template_id}: registration_number か payee_id の"
                f"どちらかが必要です（引けないテンプレートは使えません）")

    def boxes_for(self, image_size: tuple[int, int]) -> dict[str, Box]:
        """実画像の大きさに合わせて座標を比例させる。"""
        rw, rh = self.reference_size
        iw, ih = image_size
        if (iw, ih) == (rw, rh):
            return dict(self.fields)

        sx, sy = iw / rw, ih / rh
        # 縦横比が大きく違う画像は、別の様式か向きが違う。黙って読まない。
        if abs(sx - sy) / max(sx, sy) > 0.02:
            raise ValidationError(
                f"{self.template_id}: 画像の縦横比が基準と違います"
                f"（基準 {rw}x{rh} / 実際 {iw}x{ih}）。"
                f"向きや様式を確認してください。")
        return {name: (round(x0 * sx), round(y0 * sy),
                       round(x1 * sx), round(y1 * sy))
                for name, (x0, y0, x1, y1) in self.fields.items()}

    @property
    def is_verified(self) -> bool:
        return bool(self.verified_on and self.verified_by)


class TemplateSet:
    def __init__(self, templates: list[Template]):
        self._by_id: dict[str, Template] = {}
        self._by_reg: dict[str, Template] = {}
        self._by_payee: dict[str, Template] = {}
        for t in templates:
            t.validate()
            if t.template_id in self._by_id:
                raise ValidationError(f"template_id が重複: {t.template_id}")
            self._by_id[t.template_id] = t
            if t.registration_number:
                key = normalize_tnumber(t.registration_number)
                if key in self._by_reg:
                    raise ValidationError(
                        f"登録番号 {key} が {self._by_reg[key].template_id} と "
                        f"{t.template_id} で重複しています")
                self._by_reg[key] = t
            if t.payee_id:
                if t.payee_id in self._by_payee:
                    raise ValidationError(
                        f"payee_id {t.payee_id} のテンプレートが重複しています")
                self._by_payee[t.payee_id] = t

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self) -> list[Template]:
        return list(self._by_id.values())

    def find(self, *, registration_number: str = "",
             payee_id: str = "") -> Template | None:
        """完全一致のみ。引けなければ None（＝人へ）。"""
        if registration_number:
            try:
                key = normalize_tnumber(registration_number)
            except ValidationError:
                return None
            if key in self._by_reg:
                return self._by_reg[key]
        if payee_id and payee_id in self._by_payee:
            return self._by_payee[payee_id]
        return None


def load_templates(path: str | Path) -> TemplateSet:
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"テンプレートファイルがありません: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValidationError(f"{p}: JSON として読めません: {e}") from e

    if raw.get("version") != 1:
        raise ValidationError(
            f"{p}: version が 1 ではありません: {raw.get('version')!r}")

    out: list[Template] = []
    for i, item in enumerate(raw.get("templates", [])):
        try:
            out.append(Template(
                template_id=item["template_id"],
                display_name=item.get("display_name", ""),
                reference_size=tuple(item["reference_size"]),
                fields={k: tuple(v) for k, v in item["fields"].items()},
                page=int(item.get("page", 1)),
                required_fields=list(item.get("required_fields", [])),
                registration_number=item.get("registration_number", ""),
                payee_id=item.get("payee_id", ""),
                verified_on=item.get("verified_on", ""),
                verified_by=item.get("verified_by", ""),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise ValidationError(
                f"{p}: templates[{i}] の項目が不正です: {e}") from e
    return TemplateSet(out)


# ===== format.py ======================================================
"""全銀協規定形式 (総合振込 / 種別コード 21) record writer.

The field tables below are declared as data so they can be diffed field-by-field
against the bank's own published spec. Each table is asserted to total exactly
120 bytes at import time.

SPEC SOURCE TO VERIFY AGAINST:
    鹿児島銀行 FB-Webサービス（総合振込）全銀レコードフォーマット
    https://www.kagin.co.jp/library/img/fb_manual/19_14_01.pdf

The layout here is the 全銀協 standard, which regional banks implement with
small local variations (most often in 振込指定区分 / 識別表示 at bytes 112-113,
and in whether 手形交換所番号 is zero-filled or space-filled). Confirm those two
against the PDF before the first live run - see FIELD NOTES at the bottom.
"""




RECORD_LENGTH = 120

# Justification / padding behaviour.
NUM = "N"    # numeric: right-justified, zero-filled
CHR = "C"    # character: left-justified, space-filled


@dataclass(frozen=True)
class Field:
    seq: int
    name: str
    kind: str
    length: int


HEADER_FIELDS = (
    Field(1, "データ区分", NUM, 1),
    Field(2, "種別コード", NUM, 2),
    Field(3, "コード区分", NUM, 1),
    Field(4, "委託者コード", NUM, 10),
    Field(5, "委託者名", CHR, 40),
    Field(6, "取組日", NUM, 4),
    Field(7, "仕向銀行番号", NUM, 4),
    Field(8, "仕向銀行名", CHR, 15),
    Field(9, "仕向支店番号", NUM, 3),
    Field(10, "仕向支店名", CHR, 15),
    Field(11, "預金種目", NUM, 1),
    Field(12, "口座番号", NUM, 7),
    Field(13, "ダミー", CHR, 17),
)

DATA_FIELDS = (
    Field(1, "データ区分", NUM, 1),
    Field(2, "被仕向銀行番号", NUM, 4),
    Field(3, "被仕向銀行名", CHR, 15),
    Field(4, "被仕向支店番号", NUM, 3),
    Field(5, "被仕向支店名", CHR, 15),
    Field(6, "手形交換所番号", CHR, 4),
    Field(7, "預金種目", NUM, 1),
    Field(8, "口座番号", NUM, 7),
    Field(9, "受取人名", CHR, 30),
    Field(10, "振込金額", NUM, 10),
    Field(11, "新規コード", NUM, 1),
    Field(12, "顧客コード1", CHR, 10),
    Field(13, "顧客コード2", CHR, 10),
    Field(14, "振込指定区分", CHR, 1),
    Field(15, "識別表示", CHR, 1),
    Field(16, "ダミー", CHR, 7),
)

TRAILER_FIELDS = (
    Field(1, "データ区分", NUM, 1),
    Field(2, "合計件数", NUM, 6),
    Field(3, "合計金額", NUM, 12),
    Field(4, "ダミー", CHR, 101),
)

END_FIELDS = (
    Field(1, "データ区分", NUM, 1),
    Field(2, "ダミー", CHR, 119),
)

for _table_name, _table in (
    ("HEADER", HEADER_FIELDS), ("DATA", DATA_FIELDS),
    ("TRAILER", TRAILER_FIELDS), ("END", END_FIELDS),
):
    _total = sum(f.length for f in _table)
    assert _total == RECORD_LENGTH, (
        f"{_table_name} record is {_total} bytes, must be {RECORD_LENGTH}")


def field_offsets(table: tuple[Field, ...]) -> list[tuple[Field, int, int]]:
    """Return (field, start, end) 1-based inclusive byte positions."""
    out, pos = [], 1
    for f in table:
        out.append((f, pos, pos + f.length - 1))
        pos += f.length
    return out


def _fit(value: str, f: Field) -> str:
    """Pad or reject `value` for field `f`. Never truncates silently."""
    n = byte_length(value)
    if n > f.length:
        raise ValidationError(
            f"項番{f.seq} {f.name}: {value!r} は {n} バイトで、"
            f"上限 {f.length} バイトを超えています。"
            f"振込先マスタで短縮名を指定してください（自動切り詰めは行いません）。"
        )
    if f.kind == NUM:
        return "0" * (f.length - n) + value
    return value + " " * (f.length - n)


def _build(table: tuple[Field, ...], values: dict[str, str]) -> str:
    parts = []
    for f in table:
        raw = values.get(f.name, "")
        parts.append(_fit(raw, f))
    line = "".join(parts)
    n = byte_length(line)
    if n != RECORD_LENGTH:
        raise ValidationError(f"レコード長が {n} バイトです（120でなければなりません）")
    return line


def build_header(batch: TransferBatch) -> str:
    r = batch.requester
    return _build(HEADER_FIELDS, {
        "データ区分": "1",
        "種別コード": "21",
        "コード区分": "0",
        "委託者コード": r.consignor_code,
        "委託者名": r.name_kana,
        "取組日": f"{batch.transfer_date.month:02d}{batch.transfer_date.day:02d}",
        "仕向銀行番号": r.bank_code,
        "仕向銀行名": r.bank_name_kana,
        "仕向支店番号": r.branch_code,
        "仕向支店名": r.branch_name_kana,
        "預金種目": r.deposit_type,
        "口座番号": r.account_number,
        "ダミー": "",
    })


def build_data(p) -> str:
    return _build(DATA_FIELDS, {
        "データ区分": "2",
        "被仕向銀行番号": p.bank_code,
        "被仕向銀行名": p.bank_name_kana,
        "被仕向支店番号": p.branch_code,
        "被仕向支店名": p.branch_name_kana,
        "手形交換所番号": "",
        "預金種目": p.deposit_type,
        "口座番号": p.account_number,
        "受取人名": p.payee_name_kana,
        "振込金額": str(p.amount),
        "新規コード": p.new_code,
        # 識別表示="Y" のとき 92-111 は EDI情報。それ以外は顧客コード1・2。
        "顧客コード1": (p.edi_info[:10] if p.edi_info else p.customer_code_1),
        "顧客コード2": (p.edi_info[10:20] if p.edi_info else p.customer_code_2),
        "振込指定区分": p.transfer_kind,
        "識別表示": p.identifier,
        "ダミー": "",
    })


def build_trailer(batch: TransferBatch) -> str:
    return _build(TRAILER_FIELDS, {
        "データ区分": "8",
        "合計件数": str(batch.total_count),
        "合計金額": str(batch.total_amount),
        "ダミー": "",
    })


def build_end() -> str:
    return _build(END_FIELDS, {"データ区分": "9", "ダミー": ""})


def build_records(batch: TransferBatch) -> list[str]:
    batch.validate()
    records = [build_header(batch)]
    records += [build_data(p) for p in batch.payments]
    records.append(build_trailer(batch))
    records.append(build_end())
    return records


def render(batch: TransferBatch, *, newline: str = "\r\n",
           trailing_newline: bool = True) -> bytes:
    """Render the batch as Shift_JIS bytes.

    `newline` defaults to CRLF, which is what FB-Web style uploads expect.
    Some transmission modes want a pure 120-byte block stream with no line
    breaks at all - pass newline="" for that.
    """
    records = build_records(batch)
    body = newline.join(records)
    if trailing_newline and newline:
        body += newline
    return body.encode("cp932")


# ---------------------------------------------------------------------------
# FIELD NOTES - the three things to confirm against the 鹿児島銀行 PDF
# ---------------------------------------------------------------------------
# 1. 手形交換所番号 (data, bytes 39-42): written here as spaces. Some banks
#    specify zero-fill. If the PDF says "0000", change the field kind to NUM.
# 2. 振込指定区分 (data, byte 112): RESOLVED. The clinic's own 総合振込送信
#    データ一覧 (2026-08-31 run, 116 件) prints 振込指定区分 = 電信振込 for
#    every record, so "7" is the value in use ("8" = 文書振込).
#    識別表示 (byte 113): RESOLVED, and it is NOT a fee flag - "Y" means
#    EDI情報を使用する, which re-purposes bytes 92-111 as a 20-digit EDI
#    field. 全銀フォーマットには振込手数料の項目がない: 先方負担は
#    アップロード画面で指定し、ファイル内の全明細に一括適用される.
# 3. 改行 and EOF: CRLF per record by default, no 0x1A EOF byte. If the bank's
#    uploader rejects the file, the usual culprits are (in order) a trailing
#    newline, a missing one, or a 0x1A the uploader does not expect.


# ===== master.py ======================================================
"""振込先マスタ - the single source of truth for bank details.

Bank coordinates NEVER come from an invoice. They come from this file, which a
human populates once per payee from that payee's own 振込先案内 / 通帳 and signs
off on (確認日 / 確認者). An invoice can change what you pay; it can never change
where you pay.
"""




PAYEE_COLUMNS = [
    "payee_id", "display_name", "bank_code", "bank_name_kana",
    "branch_code", "branch_name_kana", "deposit_type", "account_number",
    "payee_name_kana", "fee_borne_by", "verified_on", "verified_by",
]


@dataclass
class Payee:
    payee_id: str
    display_name: str
    bank_code: str
    bank_name_kana: str
    branch_code: str
    branch_name_kana: str
    deposit_type: str
    account_number: str
    payee_name_kana: str
    fee_borne_by: str          # "sender" or "beneficiary"
    verified_on: date | None
    verified_by: str
    conversion_notes: list[str]
    # FB-Web 受取人マスタの顧客コード。28.4%が空欄なので既定は空。
    customer_code_1: str = ""
    customer_code_2: str = ""
    # 適格請求書発行事業者登録番号。請求書から業者を引くための照合キー。
    # 国税庁には問い合わせない（院内は閉鎖環境）。マスタ内の完全一致のみ。
    registration_number: str = ""

    @property
    def is_verified(self) -> bool:
        return self.verified_on is not None and bool(self.verified_by.strip())


def load_payees(path: str | Path) -> dict[str, Payee]:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in PAYEE_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValidationError(
                f"{path}: 必須列がありません: {', '.join(missing)}")

        payees: dict[str, Payee] = {}
        for lineno, row in enumerate(reader, start=2):
            pid = (row["payee_id"] or "").strip()
            if not pid:
                raise ValidationError(f"{path}:{lineno}: payee_id が空です")
            if pid in payees:
                raise ValidationError(f"{path}:{lineno}: payee_id が重複: {pid}")

            notes: list[str] = []
            raw_name = (row["payee_name_kana"] or "").strip()
            if not raw_name:
                raise ValidationError(f"{path}:{lineno}: {pid}: payee_name_kana が空です")
            try:
                converted = to_zengin_kana(raw_name)
            except KanaError as e:
                raise ValidationError(f"{path}:{lineno}: {pid}: {e}") from e
            notes.extend(converted.notes)

            bank_name = to_zengin_kana((row["bank_name_kana"] or "").strip())
            branch_name = to_zengin_kana((row["branch_name_kana"] or "").strip())

            deposit_type = (row["deposit_type"] or "").strip()
            if deposit_type not in DEPOSIT_TYPES:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: deposit_type が不正: {deposit_type!r} "
                    f"(1=普通 2=当座 4=貯蓄 9=その他)")

            fee = (row["fee_borne_by"] or "sender").strip().lower()
            if fee not in ("sender", "beneficiary"):
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: fee_borne_by は sender / beneficiary: {fee!r}")

            reg_raw = (row.get("registration_number") or "").strip()
            reg = ""
            if reg_raw:
                try:
                    reg = normalize_tnumber(reg_raw)
                except ValidationError as e:
                    raise ValidationError(f"{path}:{lineno}: {pid}: {e}") from e

            verified_raw = (row["verified_on"] or "").strip()
            verified_on = None
            if verified_raw:
                try:
                    verified_on = datetime.strptime(verified_raw, "%Y-%m-%d").date()
                except ValueError as e:
                    raise ValidationError(
                        f"{path}:{lineno}: {pid}: verified_on は YYYY-MM-DD: "
                        f"{verified_raw!r}") from e

            payees[pid] = Payee(
                payee_id=pid,
                display_name=(row["display_name"] or "").strip(),
                bank_code=(row["bank_code"] or "").strip().zfill(4),
                bank_name_kana=bank_name.text,
                branch_code=(row["branch_code"] or "").strip().zfill(3),
                branch_name_kana=branch_name.text,
                deposit_type=deposit_type,
                account_number=(row["account_number"] or "").strip(),
                payee_name_kana=converted.text,
                fee_borne_by=fee,
                customer_code_1=(row.get("customer_code_1") or "").strip(),
                customer_code_2=(row.get("customer_code_2") or "").strip(),
                registration_number=reg,
                verified_on=verified_on,
                verified_by=(row["verified_by"] or "").strip(),
                conversion_notes=notes,
            )
    return payees


def registration_index(payees: dict[str, Payee]) -> dict[str, str]:
    """{正規化済みT番号: payee_id}。請求書の登録番号から業者を引くため。

    同じ番号が2社に付いていたら止める（登録ミス。黙って片方を選ばない）。
    """
    index: dict[str, str] = {}
    for pid, p in payees.items():
        if not p.registration_number:
            continue
        if p.registration_number in index:
            raise ValidationError(
                f"登録番号 {p.registration_number} が "
                f"{index[p.registration_number]} と {pid} で重複しています")
        index[p.registration_number] = pid
    return index


# ===== invoices.py ====================================================
"""Invoice intake and aggregation.

An "invoice row" is the normalised result of reading one 請求書. How that row is
produced (per-vendor template parser, manual entry, an OCR pass) is out of scope
here on purpose: this module only ever sees payee_id + amount + provenance, so
the money path stays identical regardless of how the document was read.
"""




INVOICE_COLUMNS = ["payee_id", "invoice_no", "invoice_date",
                    "amount", "source_file"]


@dataclass
class InvoiceRow:
    payee_id: str
    invoice_no: str
    invoice_date: date
    amount: int
    source_file: str
    memo: str = ""


@dataclass
class Anomaly:
    payee_id: str
    kind: str
    message: str


def load_invoices(path: str | Path) -> list[InvoiceRow]:
    path = Path(path)
    rows: list[InvoiceRow] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in INVOICE_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValidationError(f"{path}: 必須列がありません: {', '.join(missing)}")

        for lineno, row in enumerate(reader, start=2):
            pid = (row["payee_id"] or "").strip()
            inv_no = (row["invoice_no"] or "").strip()
            if not pid:
                raise ValidationError(f"{path}:{lineno}: payee_id が空です")

            key = (pid, inv_no)
            if inv_no and key in seen:
                raise ValidationError(
                    f"{path}:{lineno}: 請求書番号が重複しています: {pid} / {inv_no}。"
                    f"二重振込を防ぐため処理を中止します。")
            seen.add(key)

            raw_amount = (row["amount"] or "").strip().replace(",", "").replace("\\", "")
            raw_amount = raw_amount.replace("¥", "").replace("円", "")
            try:
                amount = int(raw_amount)
            except ValueError as e:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: amount が整数ではありません: "
                    f"{row['amount']!r}") from e

            raw_date = (row["invoice_date"] or "").strip()
            try:
                inv_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError as e:
                raise ValidationError(
                    f"{path}:{lineno}: {pid}: invoice_date は YYYY-MM-DD: "
                    f"{raw_date!r}") from e

            rows.append(InvoiceRow(
                payee_id=pid, invoice_no=inv_no, invoice_date=inv_date,
                amount=amount, source_file=(row["source_file"] or "").strip(),
                memo=(row.get("memo") or "").strip(),
            ))
    return rows


def detect_anomalies(rows: list[InvoiceRow],
                     history: dict[str, list[int]] | None = None,
                     *, sigma: float = 2.0) -> list[Anomaly]:
    """人の目を向けさせる先を挙げる。統計計算のみでモデルは使わない。

    判定の本体は history.py（平均±2σ と 中央値+MAD の併走）。
    ここは請求書行を支払先ごとに合算して渡すだけ。
    フラグは処理を止めない。振込一覧表に印をつけるだけ。
    """

    out: list[Anomaly] = []
    for r in rows:
        if r.amount <= 0:
            out.append(Anomaly(r.payee_id, "amount",
                               f"請求額が0以下です ({r.amount:,}円 / {r.invoice_no})"))

    totals: dict[str, int] = {}
    for r in rows:
        totals[r.payee_id] = totals.get(r.payee_id, 0) + r.amount

    h = History(history or {})
    for pid, total in totals.items():
        a = h.assess(pid, total, sigma=sigma)
        if not a.needs_review:
            continue
        past = h.amounts(pid)
        if not past:
            kind = "new_payee"
        elif len(past) < 3:
            kind = "short_history"
        elif a.stats.get("sd") == 0:
            kind = "changed"
        else:
            kind = "outlier"
        for reason in a.reasons:
            out.append(Anomaly(pid, kind, reason))

    return out


def aggregate(rows: list[InvoiceRow], payees: dict[str, Payee],
              *, require_verified: bool = True,
              route=None, fee_policy=None) -> list[Payment]:
    """Group invoice rows into one Payment per payee.

    `route` decides how a 先方負担 fee is handled (see zengin.fees); it
    defaults to the 全銀 file route, which nets the fee here.
    """

    if route is None:
        route = Route.ZENGIN

    grouped: dict[str, list[InvoiceRow]] = {}
    for r in rows:
        grouped.setdefault(r.payee_id, []).append(r)

    payments: list[Payment] = []
    for pid in sorted(grouped):
        if pid not in payees:
            raise ValidationError(
                f"振込先マスタに payee_id {pid!r} がありません。"
                f"マスタに登録し、口座を人が確認してから再実行してください。")
        p = payees[pid]
        if require_verified and not p.is_verified:
            raise ValidationError(
                f"{pid} ({p.display_name}): 口座の確認欄 (verified_on / verified_by) "
                f"が空です。未確認の口座には振り込めません。")

        items = grouped[pid]
        invoice_total = sum(i.amount for i in items)
        total, fee = resolve_amount(
            invoice_total, fee_borne_by=p.fee_borne_by, route=route,
            policy=fee_policy, bank_code=p.bank_code,
            branch_code=p.branch_code)
        extra_notes = []
        if fee:
            extra_notes.append(
                f"先方負担: 請求 {invoice_total:,}円 − 手数料 {fee:,}円 "
                f"= 振込 {total:,}円")
        payments.append(Payment(
            payee_id=pid,
            bank_code=p.bank_code,
            bank_name_kana=p.bank_name_kana,
            branch_code=p.branch_code,
            branch_name_kana=p.branch_name_kana,
            deposit_type=p.deposit_type,
            account_number=p.account_number,
            payee_name_kana=p.payee_name_kana,
            amount=total,
            payee_name_display=p.display_name,
            source_documents=[i.source_file for i in items if i.source_file],
            notes=list(p.conversion_notes) + extra_notes,
        ))
    return payments


# ===== amounts.py =====================================================
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


# ===== ocr.py =========================================================
"""スキャン請求書から金額を読む（多数決つき）。

Tesseract は1回の読み取りでは信用できない。実物の請求書で測ったところ、
設定を変えた11通りのうち4通りが誤読した（表の罫線を "1" と読み、
376,772 を 3,767,721 にした）。**桁が1つ増えても、見た目は自然な数字になる。**

そこで、同じ場所を**複数の設定で読み、一致したものだけ採用する**。
一致しなければ「読めなかった」として人に回す。読めた数字が
正しいかどうかは、さらに reconcile.py の検算が決める。

  読む（複数回） → 全部一致？ → 検算に通る？ → 採用
                     ↓ いいえ      ↓ いいえ
                    人へ          人へ

外部通信なし。Tesseract はローカルで動く画像認識であり、生成AIではない。
"""




# 読み取り設定。psm 7=1行, 8=1語。倍率2倍は罫線を拾いやすいので入れない
# （実測で 3767721 の誤読を出した）。
VARIANTS = [
    {"psm": 7, "lang": "eng", "whitelist": "0123456789,", "scale": 1},
    {"psm": 7, "lang": "eng", "whitelist": None, "scale": 1},
    {"psm": 8, "lang": "eng", "whitelist": "0123456789,", "scale": 4},
    {"psm": 7, "lang": "eng", "whitelist": "0123456789,", "scale": 4},
]


@dataclass
class CellRead:
    """1つの欄の読み取り結果。"""

    label: str
    value: int | None                  # 全設定が一致したときだけ入る
    votes: dict[int, int] = field(default_factory=dict)
    raw: list[str] = field(default_factory=list)

    @property
    def agreed(self) -> bool:
        return self.value is not None

    @property
    def why(self) -> str:
        if self.agreed:
            return "一致"
        if not self.votes:
            return "数字が読めなかった"
        got = ", ".join(f"{v:,}({n}票)" for v, n in
                        sorted(self.votes.items(), key=lambda x: -x[1]))
        return f"読み取りが割れた: {got}"


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _digits(text: str) -> list[int]:
    out = []
    for m in re.findall(r"\d[\d,. ]*\d|\d", text):
        s = re.sub(r"[,. ]", "", m)
        if s.isdigit():
            out.append(int(s))
    return out


def read_cell(image, box: tuple[int, int, int, int], label: str,
              *, require_unanimous: bool = True) -> CellRead:
    """1つの欄を複数設定で読み、一致した値だけ返す。

    require_unanimous=True のとき、全設定が同じ1つの数字を出した場合のみ
    採用する。1つでも違えば None（＝人に回す）。
    """
    from PIL import Image, ImageOps

    crop = image.crop(box).convert("L")
    votes: Counter[int] = Counter()
    raws: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "cell.png"
        for v in VARIANTS:
            img = crop
            if v["scale"] != 1:
                img = crop.resize((crop.width * v["scale"],
                                   crop.height * v["scale"]))
                img = ImageOps.autocontrast(img).point(
                    lambda p: 0 if p < 140 else 255)
            img.save(tmp)
            cmd = ["tesseract", str(tmp), "stdout",
                   "--psm", str(v["psm"]), "-l", v["lang"]]
            if v["whitelist"]:
                cmd += ["-c", f"tessedit_char_whitelist={v['whitelist']}"]
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=30).stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
            raws.append(out.strip().replace("\n", " "))
            found = _digits(out)
            # 欄に数字が1つだけ写っている前提。複数出たら罫線を拾っている
            if len(found) == 1:
                votes[found[0]] += 1

    value = None
    if votes:
        if require_unanimous:
            if len(votes) == 1 and sum(votes.values()) == len(VARIANTS):
                value = next(iter(votes))
        else:
            top, n = votes.most_common(1)[0]
            if n > len(VARIANTS) / 2:
                value = top

    return CellRead(label=label, value=value, votes=dict(votes), raw=raws)


def read_cells(image_path: str | Path,
               boxes: dict[str, tuple[int, int, int, int]],
               **kw) -> dict[str, CellRead]:
    """テンプレートで決まった複数の欄をまとめて読む。"""
    if not tesseract_available():
        raise ValidationError(
            "tesseract が見つかりません。OCRなしで運用する場合は "
            "金額を手入力してください。")
    from PIL import Image

    image = Image.open(image_path)
    return {label: read_cell(image, box, label, **kw)
            for label, box in boxes.items()}


# ===== readers.py =====================================================
"""読み取り器の差し替え口と、二重読みによる合意判定。

**読み取り器は信用しない。合意と検算を信用する。**

Tesseract も VLM も、単独では桁を誤る。実測で Tesseract は設定違い11通り中
4通りが誤読した（罫線を "1" と読み 376,772 → 3,767,721）。VLM も数字の
読み違いが知られている。どちらも「もっともらしい間違った数字」を出す。

そこで **仕組みの違う2つの読み手に同じ欄を読ませ、一致したときだけ採用**する。
Tesseract（パターン認識）と VLM（生成モデル）は誤り方が違うので、
同じ間違いを同時に起こす確率は、片方が間違う確率よりずっと低い。

    Tesseract ─┐
               ├→ 一致した？ ─Yes→ 検算 ─通った→ 2σ判定 ─→ 採用
    VLM       ─┘      │No                │不通                │外れ
                      ↓                  ↓                    ↓
                     人へ                人へ              印をつけて人へ

VLM は localhost の Ollama のみ。データは機内から出ない。
（tests/test_offline_guarantee.py が URL を機械検査する）
"""




# Ollama のローカル既定。ここ以外を指せないよう、テストで検査している。
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


class FieldReader(Protocol):
    """1つの欄から数字の候補を返すもの。"""

    name: str

    def read(self, image_path: str, box: tuple[int, int, int, int],
             label: str) -> list[int]:
        ...


@dataclass
class TesseractReader:
    """既存の多数決OCR。設定違いで複数回読み、全一致した値だけ返す。"""

    name: str = "tesseract"

    def read(self, image_path, box, label) -> list[int]:
        from PIL import Image
        r = read_cell(Image.open(image_path), box, label)
        return [r.value] if r.agreed else []


@dataclass
class RapidOcrReader:
    """RapidOCR（PP-OCRv4）で読む。モデルを同梱しており取得不要。

    実測（実物のスキャン請求書・7欄）:
        Tesseract 3/7 正解 / RapidOCR 7/7 正解
    Tesseract が読めなかった 592,438 や 繰越額 0 も読めた。
    ただし **標本は請求書1通ぶん**であり、一般の精度を示すものではない。
    院内で複数業者にかけて測り直すこと（measure モード）。

    生成モデルではない（CNN/CRNN 系の画像認識）。外部通信もしない。
    枠が分割されることがある（"376." と "772"）ので左から連結する。
    """

    name: str = "rapidocr"
    pad: int = 30              # 切り出しが小さすぎると文字検出が働かない
    min_confidence: float = 0.5
    _engine: object = None

    def _ocr(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as e:
                raise ValidationError(
                    "rapidocr-onnxruntime が入っていません。"
                    "オフライン導入手順は README を参照してください。") from e
            self._engine = RapidOCR()
        return self._engine

    def read(self, image_path, box, label) -> list[int]:
        import numpy as np
        from PIL import Image

        x0, y0, x1, y1 = box
        img = Image.open(image_path)
        arr = np.array(img.crop((max(0, x0 - self.pad), max(0, y0 - self.pad),
                                 x1 + self.pad, y1 + self.pad)).convert("RGB"))
        res, _ = self._ocr()(arr)
        if not res:
            return []
        parts = sorted(res, key=lambda r: r[0][0][0])
        if min(float(p[2]) for p in parts) < self.min_confidence:
            return []
        found = _digits("".join(str(p[1]) for p in parts))
        return [found[0]] if len(found) == 1 else []


@dataclass
class OllamaVisionReader:
    """localhost の Ollama で画像から数字を読む。

    **この実装は未検証である。** 開発環境から Ollama のモデルを取得できず
    （ollama.com / registry.ollama.ai / huggingface.co が遮断）、精度を
    measure.py で実測していない。院内で実データにかけて測ること。
    精度が出なくても安全性は変わらない（合意・検算・2σ が効くため）が、
    自動で通る率は変わる。
    """

    model: str = "qwen2.5vl:3b"
    name: str = "ollama"
    timeout: int = 120
    attempts: int = 2          # 同じ画像を複数回読ませ、揺れを検出する

    PROMPT = (
        "この画像は請求書の金額欄を切り出したものです。"
        "写っている数字を、そのまま1つだけ半角数字で答えてください。"
        "カンマ・円記号・説明は書かず、数字だけを出力してください。"
        "読み取れない場合は UNKNOWN とだけ答えてください。"
    )

    def read(self, image_path, box, label) -> list[int]:
        import base64
        import io
        import urllib.request
        from PIL import Image

        buf = io.BytesIO()
        Image.open(image_path).crop(box).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        seen: list[int] = []
        for _ in range(self.attempts):
            payload = json.dumps({
                "model": self.model, "prompt": self.PROMPT,
                "images": [b64], "stream": False,
                "options": {"temperature": 0},
            }).encode()
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = json.loads(r.read().decode())
            except Exception as e:                     # noqa: BLE001
                raise ValidationError(
                    f"Ollama に接続できません（{OLLAMA_URL}）: {e}。"
                    f"`ollama serve` が動いているか確認してください。") from e
            found = _digits(body.get("response", ""))
            if len(found) == 1:
                seen.append(found[0])

        # 複数回読んで揺れたら採用しない
        if len(seen) == self.attempts and len(set(seen)) == 1:
            return [seen[0]]
        return []


@dataclass
class CrossRead:
    label: str
    value: int | None
    per_reader: dict[str, list[int]] = field(default_factory=dict)

    @property
    def agreed(self) -> bool:
        return self.value is not None

    @property
    def why(self) -> str:
        if self.agreed:
            return "両方が一致"
        parts = []
        for name, vals in self.per_reader.items():
            parts.append(f"{name}={vals[0]:,}" if vals else f"{name}=読めず")
        return "不一致: " + " / ".join(parts)


def cross_read(image_path: str, box: tuple[int, int, int, int], label: str,
               readers: list[FieldReader]) -> CrossRead:
    """複数の読み手に同じ欄を読ませ、**全員が同じ1つの数字**を出した時だけ採用。

    1人でも読めなかった、または食い違ったら None（＝人へ）。
    読み手を増やすほど自動通過率は下がり、安全側に倒れる。
    """
    if not readers:
        raise ValidationError("読み取り器が指定されていません")

    per: dict[str, list[int]] = {}
    for r in readers:
        per[r.name] = r.read(image_path, box, label)

    values = [v[0] for v in per.values() if len(v) == 1]
    ok = len(values) == len(readers) and len(set(values)) == 1
    return CrossRead(label=label, value=values[0] if ok else None,
                     per_reader=per)


# 読み取り器の選び方
#   "rapidocr"          既定。実測で最良（実物7欄中7正解）。モデル同梱・取得不要
#   "rapidocr+tesseract" 2つの一致のみ採用。自動通過率は下がるが安全側
#   "ollama"            VLM。**未検証**。RapidOCR で足りない業者が出た場合の控え
#   "rapidocr+ollama"   上の2つの一致のみ採用
#   "tesseract"         比較用
PRESETS = {
    "rapidocr": ["rapidocr"],
    "tesseract": ["tesseract"],
    "ollama": ["ollama"],
    "rapidocr+tesseract": ["rapidocr", "tesseract"],
    "rapidocr+ollama": ["rapidocr", "ollama"],
    "all": ["rapidocr", "tesseract", "ollama"],
}


def make_readers(preset: str = "rapidocr", *, ollama_model: str | None = None
                 ) -> list[FieldReader]:
    """名前から読み取り器を組み立てる。

    VLM(ollama) は**未検証**のため既定には入れない。RapidOCR で読めない
    業者が出たときの控えとして選べるようにしてある。どれを選んでも、
    後段の検算と2σ判定は同じように効く。
    """
    if preset not in PRESETS:
        raise ValidationError(
            f"読み取り器の指定が不正です: {preset!r}。"
            f"選べるのは {', '.join(sorted(PRESETS))}")

    built: list[FieldReader] = []
    for name in PRESETS[preset]:
        if name == "rapidocr":
            built.append(RapidOcrReader())
        elif name == "tesseract":
            built.append(TesseractReader())
        elif name == "ollama":
            built.append(OllamaVisionReader(model=ollama_model)
                         if ollama_model else OllamaVisionReader())
    return built


# ===== xlsx.py ========================================================
"""Minimal zero-dependency .xlsx writer.

An .xlsx file is a zip of XML parts. The clinic environment is closed (no
pip install), so this writes the few parts Excel needs rather than depending
on openpyxl. Supports strings, integers, bold headers and a yen number format
- which is all the review sheet requires.
"""



STYLE_DEFAULT = 0
STYLE_HEADER = 1
STYLE_YEN = 2
STYLE_YEN_BOLD = 3


def _col_letter(idx: int) -> str:
    """0-based column index -> A, B, ... Z, AA, AB ..."""
    out = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WB_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="176" formatCode="&quot;\\&quot;#,##0"/></numFmts>
<fonts count="2">
<font><sz val="11"/><name val="Yu Gothic"/></font>
<font><b/><sz val="11"/><name val="Yu Gothic"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEEEEEE"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="176" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="176" fontId="1" fillId="2" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1"/>
</cellXfs>
</styleSheet>"""


def _workbook_xml(sheet_name: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )


def _cell_xml(ref: str, value, style: int) -> str:
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, int):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = "" if value is None else str(value)
    if text == "":
        return f'<c r="{ref}"{style_attr}/>'
    return (f'<c r="{ref}"{style_attr} t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(text)}</t></is></c>')


def write_xlsx(path: str, rows: list[list], *, sheet_name: str = "Sheet1",
               styles: list[list[int]] | None = None,
               col_widths: list[int] | None = None) -> None:
    """Write `rows` to `path`. `styles` mirrors `rows` with style ids."""
    sheet_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
    ]
    if col_widths:
        cols = "".join(
            f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(col_widths))
        sheet_parts.append(f"<cols>{cols}</cols>")
    sheet_parts.append("<sheetData>")

    for r_i, row in enumerate(rows):
        cells = []
        for c_i, value in enumerate(row):
            style = 0
            if styles and r_i < len(styles) and c_i < len(styles[r_i]):
                style = styles[r_i][c_i]
            cells.append(_cell_xml(f"{_col_letter(c_i)}{r_i + 1}", value, style))
        sheet_parts.append(f'<row r="{r_i + 1}">{"".join(cells)}</row>')

    sheet_parts.append("</sheetData></worksheet>")
    sheet_xml = "".join(sheet_parts)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _workbook_xml(sheet_name))
        z.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        z.writestr("xl/styles.xml", _STYLES)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


# ===== sheet.py =======================================================
"""振込一覧表 - the sheet a human approves before anything reaches the bank.

This is the control point. It shows, for every payee: which invoice files the
amount came from, the exact bytes that will sit in the 受取人名 field, any
transformation applied to the name, and any anomaly flag. The grand total on
this sheet is the same integer written into the trailer record, so approving
the sheet is equivalent to approving the file.
"""




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


# ===== verify.py ======================================================
"""Independent re-reader for a generated 全銀 file.

This deliberately does NOT reuse format.py's writer helpers. It slices the
bytes by hard-coded offsets and recomputes the totals from scratch, so that a
bug in the writer cannot hide behind the same bug in the checker. Every file
is round-tripped through this before a human is asked to approve it.
"""



VERIFY_RECORD_LENGTH = 120  # 意図的な重複: 書き手(format.py)に依存しないため


@dataclass
class Problem:
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.where}] {self.message}"


def _split_records(raw: bytes) -> tuple[list[bytes], list[Problem]]:
    problems: list[Problem] = []
    data = raw
    if data.endswith(b"\x1a"):
        problems.append(Problem("file", "EOF文字 0x1A が末尾にあります"))
        data = data[:-1]

    if b"\r\n" in data:
        parts = data.split(b"\r\n")
    elif b"\n" in data:
        problems.append(Problem("file", "改行が LF です（通常は CRLF）"))
        parts = data.split(b"\n")
    else:
        parts = [data[i:i + VERIFY_RECORD_LENGTH]
                 for i in range(0, len(data), VERIFY_RECORD_LENGTH)]

    records = [p for p in parts if p]
    return records, problems


def verify(raw: bytes, *, expected_count: int | None = None,
           expected_total: int | None = None) -> list[Problem]:
    """Return every problem found. An empty list means the file is well-formed."""
    records, problems = _split_records(raw)

    if not records:
        return problems + [Problem("file", "レコードがありません")]

    for i, rec in enumerate(records, 1):
        if len(rec) != VERIFY_RECORD_LENGTH:
            problems.append(
                Problem(f"rec{i}", f"レコード長 {len(rec)} バイト（120でなければなりません）"))
        try:
            rec.decode("cp932")
        except UnicodeDecodeError as e:
            problems.append(Problem(f"rec{i}", f"Shift_JIS としてデコードできません: {e}"))

    kinds = [r[0:1].decode("ascii", "replace") for r in records]

    if kinds[0] != "1":
        problems.append(Problem("rec1", f"先頭がヘッダー(1)ではなく {kinds[0]!r}"))
    if kinds[-1] != "9":
        problems.append(Problem(f"rec{len(records)}", f"末尾がエンド(9)ではなく {kinds[-1]!r}"))

    header = records[0]
    if header[1:3] != b"21":
        problems.append(
            Problem("rec1", f"種別コードが 21(総合振込) ではなく {header[1:3]!r}"))
    if header[3:4] != b"0":
        problems.append(Problem("rec1", f"コード区分が 0(JIS) ではなく {header[3:4]!r}"))

    data_recs = [r for r, k in zip(records, kinds) if k == "2"]
    trailers = [r for r, k in zip(records, kinds) if k == "8"]

    if len(trailers) != 1:
        problems.append(Problem("file", f"トレーラーが {len(trailers)} 件あります（1件必要）"))

    # Recompute counts and totals straight from the data records.
    recomputed_total = 0
    for i, rec in enumerate(data_recs, 1):
        amount_raw = rec[80:90]
        try:
            amount = int(amount_raw)
        except ValueError:
            problems.append(Problem(f"data{i}", f"振込金額が数値ではありません: {amount_raw!r}"))
            continue
        if amount <= 0:
            problems.append(Problem(f"data{i}", f"振込金額が0以下です: {amount}"))
        recomputed_total += amount

        for label, sl, want_digits in (
            ("被仕向銀行番号", slice(1, 5), True),
            ("被仕向支店番号", slice(20, 23), True),
            ("口座番号", slice(43, 50), True),
        ):
            chunk = rec[sl]
            if want_digits and not chunk.isdigit():
                problems.append(Problem(f"data{i}", f"{label} が数字ではありません: {chunk!r}"))

        if rec[42:43] not in (b"1", b"2", b"4", b"9"):
            problems.append(Problem(f"data{i}", f"預金種目が不正: {rec[42:43]!r}"))

        # An all-zero account number is the classic silently-broken record.
        if rec[43:50] == b"0000000":
            problems.append(Problem(f"data{i}", "口座番号が 0000000 です"))

        name = rec[50:80]
        if not name.strip():
            problems.append(Problem(f"data{i}", "受取人名が空です"))

        kind = rec[111:112]
        if kind not in (b"7", b"8", b" "):
            problems.append(Problem(
                f"data{i}", f"振込指定区分が不正 (7=電信/8=文書): {kind!r}"))

        # 識別表示 = EDI情報使用フラグ。手数料負担先ではない。
        ident = rec[112:113]
        if ident not in (b"Y", b" "):
            problems.append(Problem(
                f"data{i}", f"識別表示は Y か空白のみ: {ident!r}"))
        if ident == b"Y" and not rec[91:111].strip():
            problems.append(Problem(
                f"data{i}", "識別表示=Y ですが EDI情報(92-111)が空です"))

    if trailers:
        t = trailers[0]
        try:
            t_count = int(t[1:7])
            t_total = int(t[7:19])
        except ValueError:
            problems.append(Problem("trailer", f"件数/金額が数値ではありません: {t[1:19]!r}"))
        else:
            if t_count != len(data_recs):
                problems.append(Problem(
                    "trailer",
                    f"合計件数 {t_count} がデータ件数 {len(data_recs)} と一致しません"))
            if t_total != recomputed_total:
                problems.append(Problem(
                    "trailer",
                    f"合計金額 {t_total:,} が明細合計 {recomputed_total:,} と一致しません"))

    if expected_count is not None and len(data_recs) != expected_count:
        problems.append(Problem(
            "file", f"データ件数 {len(data_recs)} が想定 {expected_count} と一致しません"))
    if expected_total is not None and recomputed_total != expected_total:
        problems.append(Problem(
            "file",
            f"合計金額 {recomputed_total:,} が想定 {expected_total:,} と一致しません"))

    return problems


# ===== cli.py =========================================================
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
        flagged = len({a.payee_id for a in anomalies})
        print(f"\n確認事項 {len(anomalies)} 件 / 支払先 {flagged} 先"
              f"（全 {batch.total_count} 先中）— 承認前に確認してください:")
        for a in anomalies:
            print(f"  - [{a.kind}] {a.payee_id}: {a.message}")
    else:
        print("\n確認事項: なし（全件が過去の範囲内）")
    print("\n次の手順: 振込一覧表を承認者が確認・押印 → FB-Web に全銀ファイルを送信。")
    return 0




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
          raw.split(b"\r\n")[1][112:113] == b" ")
    check("振込指定区分=7", raw.split(b"\r\n")[1][111:112] == b"7")

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



if __name__ == "__main__":
    import sys as _sys
    if "--selftest" in _sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
