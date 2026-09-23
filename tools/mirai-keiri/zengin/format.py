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

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .kana import byte_length
from .model import TransferBatch, ValidationError

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
