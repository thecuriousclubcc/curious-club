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

from dataclasses import dataclass
from dataclasses import dataclass, field
from datetime import date
from datetime import date, datetime
from datetime import datetime
from enum import Enum
from pathlib import Path
from xml.sax.saxutils import escape
import argparse
import csv
import json
import statistics
import sys
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


def normalize(code: str | None, *, width: int = WIDTH) -> str:
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
    na, nb = normalize(a), normalize(b)
    return bool(na) and na == nb


def account_key(bank_code: str, branch_code: str, deposit_type: str,
                account_number: str) -> tuple[str, str, str, str]:
    """口座の自然キー。顧客コードが未整備の先でも必ず引ける（案A）。"""
    return (bank_code.strip().zfill(4), branch_code.strip().zfill(3),
            deposit_type.strip(), account_number.strip().zfill(7))


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
                verified_on=verified_on,
                verified_by=(row["verified_by"] or "").strip(),
                conversion_notes=notes,
            )
    return payees


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
    """Flag rows that need a human's eyes before the file is built.

    Pure arithmetic - no model, no inference. A flag never blocks the run by
    itself; it marks the row in the review sheet so the approver looks at it.
    """
    out: list[Anomaly] = []
    history = history or {}

    totals: dict[str, int] = {}
    for r in rows:
        totals[r.payee_id] = totals.get(r.payee_id, 0) + r.amount

    for r in rows:
        if r.amount <= 0:
            out.append(Anomaly(r.payee_id, "amount",
                               f"請求額が0以下です ({r.amount:,}円 / {r.invoice_no})"))

    for pid, total in totals.items():
        past = history.get(pid) or []
        if len(past) < 3:
            if not past:
                out.append(Anomaly(pid, "new_payee",
                                   f"初回の支払先です（履歴なし・{total:,}円）"))
            continue
        mean = statistics.fmean(past)
        sd = statistics.pstdev(past)
        if sd == 0:
            if total != past[-1]:
                out.append(Anomaly(
                    pid, "changed",
                    f"毎回同額（{past[-1]:,}円）でしたが今回 {total:,}円 です"))
            continue
        z = (total - mean) / sd
        if abs(z) >= sigma:
            out.append(Anomaly(
                pid, "outlier",
                f"過去平均 {mean:,.0f}円 (σ={sd:,.0f}) に対し今回 {total:,}円 "
                f"— {z:+.1f}σ の乖離"))

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




HEADERS = [
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

    rows.append(list(HEADERS))
    styles.append([STYLE_HEADER] * len(HEADERS))

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
        style_row = [0] * len(HEADERS)
        style_row[9] = STYLE_YEN
        styles.append(style_row)

    rows.append([])
    styles.append([])

    total_row: list = [""] * len(HEADERS)
    total_row[0] = "合計"
    total_row[8] = f"{batch.total_count} 件"
    total_row[9] = batch.total_amount
    rows.append(total_row)
    total_styles = [STYLE_HEADER] * len(HEADERS)
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
        print(f"\n確認事項 {len(anomalies)} 件（承認前に確認してください）:")
        for a in anomalies:
            print(f"  - {a.payee_id}: {a.message}")
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
