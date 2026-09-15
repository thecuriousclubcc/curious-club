"""Independent re-reader for a generated 全銀 file.

This deliberately does NOT reuse format.py's writer helpers. It slices the
bytes by hard-coded offsets and recomputes the totals from scratch, so that a
bug in the writer cannot hide behind the same bug in the checker. Every file
is round-tripped through this before a human is asked to approve it.
"""

from __future__ import annotations

from dataclasses import dataclass

RECORD_LENGTH = 120


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
        parts = [data[i:i + RECORD_LENGTH]
                 for i in range(0, len(data), RECORD_LENGTH)]

    records = [p for p in parts if p]
    return records, problems


def verify(raw: bytes, *, expected_count: int | None = None,
           expected_total: int | None = None) -> list[Problem]:
    """Return every problem found. An empty list means the file is well-formed."""
    records, problems = _split_records(raw)

    if not records:
        return problems + [Problem("file", "レコードがありません")]

    for i, rec in enumerate(records, 1):
        if len(rec) != RECORD_LENGTH:
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
