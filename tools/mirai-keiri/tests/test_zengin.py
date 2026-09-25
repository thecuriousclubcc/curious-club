"""Tests for the 全銀 総合振込 pipeline. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zengin.format import (DATA_FIELDS, END_FIELDS, HEADER_FIELDS,
                           TRAILER_FIELDS, build_data, build_header,
                           build_trailer, build_end, field_offsets, render)
from zengin.invoices import InvoiceRow, aggregate, detect_anomalies
from zengin.kana import KanaError, byte_length, to_zengin_kana
from zengin.master import Payee
from zengin.model import (Payment, Requester, TransferBatch, ValidationError)
from zengin.verify import verify


def make_requester(**kw):
    base = dict(
        consignor_code="1234567890",
        name_kana="ｲ)ﾐﾗｲﾘﾊﾋﾞﾘﾋﾞﾖｳｲﾝ",
        bank_code="0185",
        bank_name_kana="ｶｺﾞｼﾏ",
        branch_code="101",
        branch_name_kana="ﾎﾝﾃﾝ",
        deposit_type="1",
        account_number="1234567",
    )
    base.update(kw)
    return Requester(**base)


def make_payment(**kw):
    base = dict(
        payee_id="P001",
        bank_code="0185",
        bank_name_kana="ｶｺﾞｼﾏ",
        branch_code="201",
        branch_name_kana="ﾃﾝﾓﾝｶﾝ",
        deposit_type="1",
        account_number="7654321",
        payee_name_kana="ｶ)ｻﾂﾏｼﾖｳｼﾞ",
        amount=123456,
    )
    base.update(kw)
    return Payment(**base)


def make_batch(payments=None, **kw):
    return TransferBatch(
        requester=make_requester(),
        transfer_date=kw.get("transfer_date", date(2026, 10, 31)),
        payments=payments if payments is not None else [make_payment()],
    )


class TestRecordGeometry(unittest.TestCase):
    """Every record must be exactly 120 bytes, always."""

    def test_field_tables_sum_to_120(self):
        for name, table in (("header", HEADER_FIELDS), ("data", DATA_FIELDS),
                            ("trailer", TRAILER_FIELDS), ("end", END_FIELDS)):
            self.assertEqual(sum(f.length for f in table), 120, name)

    def test_offsets_are_contiguous(self):
        for table in (HEADER_FIELDS, DATA_FIELDS, TRAILER_FIELDS, END_FIELDS):
            offsets = field_offsets(table)
            self.assertEqual(offsets[0][1], 1)
            self.assertEqual(offsets[-1][2], 120)
            for (_, _, prev_end), (_, start, _) in zip(offsets, offsets[1:]):
                self.assertEqual(start, prev_end + 1)

    def test_all_records_are_120_sjis_bytes(self):
        batch = make_batch()
        for rec in (build_header(batch), build_data(batch.payments[0]),
                    build_trailer(batch), build_end()):
            self.assertEqual(len(rec.encode("cp932")), 120)

    def test_record_length_holds_with_dakuten_heavy_name(self):
        # ﾞ/ﾟ are separate bytes; a name full of them must still fit exactly.
        p = make_payment(payee_name_kana="ﾊﾞﾋﾞﾌﾞﾍﾞﾎﾞﾊﾟﾋﾟﾌﾟﾍﾟﾎﾟﾀﾞﾁﾞﾂﾞﾃﾞﾄﾞ")
        self.assertEqual(len(build_data(p).encode("cp932")), 120)


class TestFieldPlacement(unittest.TestCase):
    """Values must land on the exact byte positions the bank reads."""

    def test_header_field_positions(self):
        rec = build_header(make_batch()).encode("cp932")
        self.assertEqual(rec[0:1], b"1")            # データ区分
        self.assertEqual(rec[1:3], b"21")           # 種別コード
        self.assertEqual(rec[3:4], b"0")            # コード区分
        self.assertEqual(rec[4:14], b"1234567890")  # 委託者コード
        self.assertEqual(rec[54:58], b"1031")       # 取組日 MMDD
        self.assertEqual(rec[58:62], b"0185")       # 仕向銀行番号
        self.assertEqual(rec[77:80], b"101")        # 仕向支店番号
        self.assertEqual(rec[95:96], b"1")          # 預金種目
        self.assertEqual(rec[96:103], b"1234567")   # 口座番号
        self.assertEqual(rec[103:120], b" " * 17)   # ダミー

    def test_data_field_positions(self):
        rec = build_data(make_payment()).encode("cp932")
        self.assertEqual(rec[0:1], b"2")
        self.assertEqual(rec[1:5], b"0185")
        self.assertEqual(rec[20:23], b"201")
        self.assertEqual(rec[42:43], b"1")
        self.assertEqual(rec[43:50], b"7654321")
        self.assertEqual(rec[80:90], b"0000123456")   # 振込金額 right-justified
        self.assertEqual(rec[90:91], b"0")            # 新規コード

    def test_amount_is_zero_padded_not_space_padded(self):
        rec = build_data(make_payment(amount=1)).encode("cp932")
        self.assertEqual(rec[80:90], b"0000000001")

    def test_account_number_short_is_left_zero_filled(self):
        rec = build_data(make_payment(account_number="123")).encode("cp932")
        self.assertEqual(rec[43:50], b"0000123")

    def test_payee_name_is_left_justified_space_filled(self):
        rec = build_data(make_payment(payee_name_kana="ｱｲｳ")).encode("cp932")
        self.assertEqual(rec[50:80], "ｱｲｳ".encode("cp932") + b" " * 27)

    def test_trailer_totals(self):
        batch = make_batch([make_payment(amount=100),
                            make_payment(payee_id="P002", amount=250)])
        rec = build_trailer(batch).encode("cp932")
        self.assertEqual(rec[0:1], b"8")
        self.assertEqual(rec[1:7], b"000002")
        self.assertEqual(rec[7:19], b"000000000350")

    def test_end_record(self):
        rec = build_end().encode("cp932")
        self.assertEqual(rec[0:1], b"9")
        self.assertEqual(rec[1:120], b" " * 119)


class TestOverflowIsRejected(unittest.TestCase):
    """Truncating a name or an amount would move money to the wrong place."""

    def test_too_long_payee_name_raises(self):
        p = make_payment(payee_name_kana="ｱ" * 31)
        with self.assertRaises(ValidationError) as cm:
            build_data(p)
        self.assertIn("受取人名", str(cm.exception))

    def test_name_of_exactly_30_bytes_is_accepted(self):
        p = make_payment(payee_name_kana="ｱ" * 30)
        self.assertEqual(len(build_data(p).encode("cp932")), 120)

    def test_dakuten_name_overflowing_30_bytes_raises(self):
        # 16 voiced kana = 32 bytes, over the 30-byte field.
        p = make_payment(payee_name_kana="ｶﾞ" * 16)
        with self.assertRaises(ValidationError):
            build_data(p)

    def test_amount_over_10_digits_raises(self):
        with self.assertRaises(ValidationError):
            make_payment(amount=10_000_000_000).validate()

    def test_float_amount_raises(self):
        with self.assertRaises(ValidationError):
            make_payment(amount=1234.0).validate()

    def test_bool_amount_raises(self):
        with self.assertRaises(ValidationError):
            make_payment(amount=True).validate()

    def test_zero_amount_raises(self):
        with self.assertRaises(ValidationError):
            make_payment(amount=0).validate()


class TestKana(unittest.TestCase):
    def test_dakuten_is_two_bytes(self):
        r = to_zengin_kana("ガ")
        self.assertEqual(r.text, "ｶﾞ")
        self.assertEqual(byte_length(r.text), 2)

    def test_small_kana_folds_to_large(self):
        r = to_zengin_kana("キャノン")
        self.assertEqual(r.text, "ｷﾔﾉﾝ")
        self.assertTrue(r.changed)

    def test_halfwidth_small_kana_folds_to_large(self):
        self.assertEqual(to_zengin_kana("ｷｬﾉﾝ").text, "ｷﾔﾉﾝ")

    def test_hiragana_converts_to_katakana(self):
        self.assertEqual(to_zengin_kana("みらい").text, "ﾐﾗｲ")

    def test_lowercase_ascii_uppercases(self):
        self.assertEqual(to_zengin_kana("abc").text, "ABC")

    def test_fullwidth_alnum_narrows(self):
        self.assertEqual(to_zengin_kana("ＡＢ１２").text, "AB12")

    def test_long_vowel_is_not_a_hyphen(self):
        self.assertEqual(to_zengin_kana("ミラー").text, "ﾐﾗｰ")
        self.assertEqual(to_zengin_kana("ミラ－").text, "ﾐﾗ-")

    def test_kanji_is_rejected_not_guessed(self):
        with self.assertRaises(KanaError):
            to_zengin_kana("株式会社")

    def test_disallowed_punctuation_is_rejected(self):
        for bad in ("ﾃｽﾄ｡", "ﾃｽﾄ･", "ﾃｽﾄ｢"):
            with self.assertRaises(KanaError):
                to_zengin_kana(bad)

    def test_every_output_char_is_one_sjis_byte(self):
        r = to_zengin_kana("ガギグゲゴパピプペポアイウabc123-. ()")
        self.assertEqual(byte_length(r.text), len(r.text))


class TestVerifier(unittest.TestCase):
    def test_clean_file_has_no_problems(self):
        batch = make_batch([make_payment(amount=100),
                            make_payment(payee_id="P002", amount=250)])
        raw = render(batch)
        self.assertEqual(verify(raw, expected_count=2, expected_total=350), [])

    def test_file_byte_length_is_exact(self):
        batch = make_batch([make_payment()])
        raw = render(batch, newline="")
        self.assertEqual(len(raw), 120 * 4)   # header + 1 data + trailer + end

    def test_crlf_file_byte_length(self):
        batch = make_batch([make_payment()])
        raw = render(batch, newline="\r\n")
        self.assertEqual(len(raw), (120 + 2) * 4)

    def test_corrupted_total_is_caught(self):
        batch = make_batch([make_payment(amount=100)])
        raw = bytearray(render(batch))
        # Corrupt the trailer's 合計金額 only.
        idx = raw.find(b"8", (120 + 2) * 2)
        trailer_start = (120 + 2) * 2
        raw[trailer_start + 7:trailer_start + 19] = b"000000009999"
        problems = verify(bytes(raw))
        self.assertTrue(any("合計金額" in str(p) for p in problems), problems)

    def test_truncated_record_is_caught(self):
        batch = make_batch([make_payment()])
        raw = render(batch, newline="")[:-10]
        problems = verify(raw)
        self.assertTrue(any("レコード長" in str(p) for p in problems), problems)

    def test_expected_total_mismatch_is_caught(self):
        batch = make_batch([make_payment(amount=100)])
        problems = verify(render(batch), expected_total=999)
        self.assertTrue(problems)

    def test_zero_account_number_is_caught(self):
        p = make_payment(account_number="0")
        batch = make_batch([p])
        problems = verify(render(batch))
        self.assertTrue(any("口座番号" in str(p) for p in problems), problems)


class TestAggregation(unittest.TestCase):
    def make_payee(self, pid="P001", **kw):
        base = dict(
            payee_id=pid, display_name="薩摩商事株式会社",
            bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
            branch_code="201", branch_name_kana="ﾃﾝﾓﾝｶﾝ",
            deposit_type="1", account_number="7654321",
            payee_name_kana="ｶ)ｻﾂﾏｼﾖｳｼﾞ", fee_borne_by="sender",
            verified_on=date(2026, 9, 1), verified_by="中村",
            conversion_notes=[],
        )
        base.update(kw)
        return Payee(**base)

    def test_multiple_invoices_sum_into_one_transfer(self):
        payees = {"P001": self.make_payee()}
        rows = [
            InvoiceRow("P001", "A-1", date(2026, 10, 1), 1000, "a.pdf"),
            InvoiceRow("P001", "A-2", date(2026, 10, 5), 2500, "b.pdf"),
        ]
        payments = aggregate(rows, payees)
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].amount, 3500)
        self.assertEqual(sorted(payments[0].source_documents), ["a.pdf", "b.pdf"])

    def test_unknown_payee_raises(self):
        rows = [InvoiceRow("NOPE", "A-1", date(2026, 10, 1), 1000, "a.pdf")]
        with self.assertRaises(ValidationError) as cm:
            aggregate(rows, {"P001": self.make_payee()})
        self.assertIn("振込先マスタ", str(cm.exception))

    def test_unverified_account_blocks_the_run(self):
        payees = {"P001": self.make_payee(verified_on=None, verified_by="")}
        rows = [InvoiceRow("P001", "A-1", date(2026, 10, 1), 1000, "a.pdf")]
        with self.assertRaises(ValidationError) as cm:
            aggregate(rows, payees)
        self.assertIn("確認", str(cm.exception))

    def test_totals_match_between_sheet_and_trailer(self):
        payees = {"P001": self.make_payee(), "P002": self.make_payee("P002")}
        rows = [
            InvoiceRow("P001", "A-1", date(2026, 10, 1), 111, "a.pdf"),
            InvoiceRow("P002", "B-1", date(2026, 10, 2), 222, "b.pdf"),
            InvoiceRow("P001", "A-2", date(2026, 10, 3), 333, "c.pdf"),
        ]
        batch = make_batch(aggregate(rows, payees))
        self.assertEqual(batch.total_amount, 666)
        self.assertEqual(batch.total_amount, sum(r.amount for r in rows))
        self.assertEqual(verify(render(batch), expected_total=666), [])


class TestAnomalies(unittest.TestCase):
    def test_new_payee_is_flagged(self):
        rows = [InvoiceRow("P001", "A-1", date(2026, 10, 1), 1000, "a.pdf")]
        kinds = {a.kind for a in detect_anomalies(rows, {})}
        self.assertIn("new_payee", kinds)

    def test_outlier_beyond_2sd_is_flagged(self):
        rows = [InvoiceRow("P001", "A-1", date(2026, 10, 1), 500_000, "a.pdf")]
        history = {"P001": [100_000, 102_000, 98_000, 101_000]}
        kinds = {a.kind for a in detect_anomalies(rows, history)}
        self.assertIn("outlier", kinds)

    def test_in_range_amount_is_not_flagged(self):
        rows = [InvoiceRow("P001", "A-1", date(2026, 10, 1), 101_000, "a.pdf")]
        history = {"P001": [100_000, 102_000, 98_000, 101_000]}
        self.assertEqual(detect_anomalies(rows, history), [])

    def test_constant_history_change_is_flagged(self):
        rows = [InvoiceRow("P001", "A-1", date(2026, 10, 1), 55_000, "a.pdf")]
        history = {"P001": [50_000, 50_000, 50_000]}
        kinds = {a.kind for a in detect_anomalies(rows, history)}
        self.assertIn("changed", kinds)


class TestDeterminism(unittest.TestCase):
    def test_same_input_produces_identical_bytes(self):
        a = render(make_batch([make_payment(), make_payment(payee_id="P002")]))
        b = render(make_batch([make_payment(), make_payment(payee_id="P002")]))
        self.assertEqual(a, b)

    def test_output_contains_no_multibyte_characters(self):
        raw = render(make_batch())
        self.assertEqual(len(raw.replace(b"\r\n", b"")), 120 * 4)
        for byte in raw:
            self.assertLess(byte, 0xE0)


if __name__ == "__main__":
    unittest.main()


class TestIdentifierIsEdiNotFee(unittest.TestCase):
    """識別表示 (byte 113) = EDI情報使用フラグ。手数料負担先ではない。"""

    def test_default_identifier_is_space(self):
        rec = build_data(make_payment()).encode("cp932")
        self.assertEqual(rec[112:113], b" ")

    def test_beneficiary_borne_fee_does_not_set_byte_113(self):
        # 先方負担でも 識別表示 は立たない。全銀に手数料の項目はない。
        p = make_payment()
        rec = build_data(p).encode("cp932")
        self.assertEqual(rec[112:113], b" ")

    def test_edi_sets_identifier_and_occupies_customer_code_area(self):
        p = make_payment(edi_info="12345678901234567890")
        rec = build_data(p).encode("cp932")
        self.assertEqual(rec[112:113], b"Y")
        self.assertEqual(rec[91:111], b"12345678901234567890")

    def test_edi_and_customer_code_cannot_coexist(self):
        p = make_payment(edi_info="123", customer_code_1="0000000480")
        with self.assertRaises(ValidationError) as cm:
            p.validate()
        self.assertIn("併用できません", str(cm.exception))

    def test_customer_code_area_holds_codes_when_no_edi(self):
        p = make_payment(customer_code_1="0000000480",
                         customer_code_2="0000000481")
        rec = build_data(p).encode("cp932")
        self.assertEqual(rec[91:101], b"0000000480")
        self.assertEqual(rec[101:111], b"0000000481")
        self.assertEqual(rec[112:113], b" ")

    def test_edi_over_20_digits_raises(self):
        with self.assertRaises(ValidationError):
            make_payment(edi_info="1" * 21).validate()


class TestFeeRouting(unittest.TestCase):
    """The two FB-Web routes net the 先方負担 fee at different points."""

    def setUp(self):
        from zengin.fees import FeePolicy
        self.policy = FeePolicy(same_branch=0, same_bank_other_branch=110,
                                other_bank=330)

    def test_sender_borne_is_invoice_amount_on_both_routes(self):
        from zengin.fees import Route, resolve_amount
        for route in (Route.SCREEN, Route.ZENGIN):
            amount, fee = resolve_amount(
                10_000, fee_borne_by="sender", route=route,
                policy=self.policy, bank_code="0001", branch_code="797")
            self.assertEqual((amount, fee), (10_000, 0), route)

    def test_screen_route_does_not_net_the_fee(self):
        from zengin.fees import Route, resolve_amount
        amount, fee = resolve_amount(
            10_000, fee_borne_by="beneficiary", route=Route.SCREEN,
            policy=self.policy, bank_code="0001", branch_code="797")
        self.assertEqual((amount, fee), (10_000, 0))

    def test_zengin_route_nets_the_fee(self):
        from zengin.fees import Route, resolve_amount
        amount, fee = resolve_amount(
            10_000, fee_borne_by="beneficiary", route=Route.ZENGIN,
            policy=self.policy, bank_code="0001", branch_code="797")
        self.assertEqual((amount, fee), (9_670, 330))

    def test_zengin_route_same_branch_is_free(self):
        from zengin.fees import Route, resolve_amount
        amount, fee = resolve_amount(
            10_000, fee_borne_by="beneficiary", route=Route.ZENGIN,
            policy=self.policy, bank_code="0185", branch_code="107")
        self.assertEqual((amount, fee), (10_000, 0))

    def test_zengin_route_without_a_fee_table_refuses(self):
        from zengin.fees import Route, resolve_amount
        with self.assertRaises(ValidationError) as cm:
            resolve_amount(10_000, fee_borne_by="beneficiary",
                           route=Route.ZENGIN, policy=None,
                           bank_code="0001", branch_code="797")
        self.assertIn("手数料テーブル", str(cm.exception))

    def test_fee_larger_than_invoice_refuses(self):
        from zengin.fees import Route, resolve_amount
        with self.assertRaises(ValidationError):
            resolve_amount(100, fee_borne_by="beneficiary", route=Route.ZENGIN,
                           policy=self.policy, bank_code="0001",
                           branch_code="797")


class TestVerifiedAgainstRealRun(unittest.TestCase):
    """Shape verified against the clinic's own 2026-08-31 総合振込送信データ一覧.

    Identifiers here are REDACTED placeholders with the real field widths.
    The live 委託者コード and 出金口座 belong in data/requester.json, which
    is gitignored - they are not committed to this repository.
    """

    def test_transfer_kind_defaults_to_denshin_furikomi(self):
        self.assertEqual(make_payment().transfer_kind, "7")

    def test_requester_matches_the_real_header(self):
        # Real run shape: 依頼人 <10桁> イ)ミライ / 0185 カゴシマ / 支店 107 セイリョウ
        r = make_requester(consignor_code="2000000000", name_kana="ｲ)ﾐﾗｲ",
                           bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                           branch_code="107", branch_name_kana="ｾｲﾘﾖｳ")
        batch = TransferBatch(requester=r, transfer_date=date(2026, 8, 31),
                              payments=[make_payment()])
        rec = build_header(batch).encode("cp932")
        self.assertEqual(rec[4:14], b"2000000000")
        self.assertEqual(rec[54:58], b"0831")
        self.assertEqual(rec[58:62], b"0185")
        self.assertEqual(rec[77:80], b"107")

    def test_a_116_record_batch_totals_correctly(self):
        payments = [make_payment(payee_id=f"P{i:03d}", amount=1000 + i)
                    for i in range(116)]
        batch = make_batch(payments, transfer_date=date(2026, 8, 31))
        raw = render(batch)
        self.assertEqual(verify(raw, expected_count=116), [])
        trailer = raw.split(b"\r\n")[-3]
        self.assertEqual(trailer[1:7], b"000116")


class TestCustomerCode(unittest.TestCase):
    """実データの 10桁/4桁 混在に耐えること。"""

    def test_short_code_pads_to_ten(self):
        from zengin.custcode import normalize_code as normalize
        self.assertEqual(normalize("9387"), "0000009387")

    def test_already_ten_digits_is_unchanged(self):
        from zengin.custcode import normalize_code as normalize
        self.assertEqual(normalize("0000000480"), "0000000480")

    def test_mixed_width_codes_match_after_normalising(self):
        from zengin.custcode import same
        self.assertTrue(same("9387", "0000009387"))
        self.assertTrue(same("2619", "0000002619"))

    def test_blank_never_matches_blank(self):
        # 28.4% の先が空欄。空欄同士を一致とみなすと誤送金になる。
        from zengin.custcode import same
        self.assertFalse(same("", ""))
        self.assertFalse(same(None, None))
        self.assertFalse(same("", "0000000010"))

    def test_non_numeric_code_raises(self):
        from zengin.custcode import normalize_code as normalize
        with self.assertRaises(ValidationError):
            normalize("A123")

    def test_overlong_code_raises(self):
        from zengin.custcode import normalize_code as normalize
        with self.assertRaises(ValidationError):
            normalize("12345678901")

    def test_account_key_is_stable_across_padding(self):
        from zengin.custcode import account_key
        self.assertEqual(account_key("185", "7", "1", "123456"),
                         account_key("0185", "007", "1", "0123456"))


class TestAmountSource(unittest.TestCase):
    """金額取込CSVの素材。列仕様が未確定でも突合材料は全部持たせる。"""

    def _batch(self):
        from zengin.invoices import InvoiceRow, aggregate
        from zengin.master import Payee
        payees = {}
        for pid, c1 in (("P001", "0000000480"), ("P002", "9387"), ("P003", "")):
            payees[pid] = Payee(
                payee_id=pid, display_name=f"テスト{pid}",
                bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                branch_code="201", branch_name_kana="ﾃﾝﾓﾝｶﾝ",
                deposit_type="1", account_number="7654321",
                payee_name_kana="ｶ)ﾃｽﾄ", fee_borne_by="sender",
                customer_code_1=c1, customer_code_2="",
                verified_on=date(2026, 9, 1), verified_by="中村",
                conversion_notes=[])
        rows = [InvoiceRow(pid, f"{pid}-1", date(2026, 10, 1), 1000, "a.pdf")
                for pid in payees]
        return make_batch(aggregate(rows, payees)), payees

    def test_short_and_long_codes_both_normalise_in_output(self):
        import csv, io, tempfile, os
        from zengin.amounts import write_amount_source
        batch, payees = self._batch()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.csv")
            write_amount_source(path, batch, payees, {"P001": 1, "P002": 1, "P003": 1})
            with open(path, encoding="cp932", newline="") as fh:
                rows = list(csv.DictReader(fh))
        by_id = {r["payee_id"]: r for r in rows}
        self.assertEqual(by_id["P001"]["顧客コード1_10桁"], "0000000480")
        self.assertEqual(by_id["P002"]["顧客コード1_10桁"], "0000009387")
        self.assertEqual(by_id["P002"]["顧客コード1_原文"], "9387")
        # 空欄は空欄のまま。勝手に埋めない。
        self.assertEqual(by_id["P003"]["顧客コード1_10桁"], "")

    def test_account_key_present_for_every_row(self):
        import csv, tempfile, os
        from zengin.amounts import write_amount_source
        batch, payees = self._batch()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.csv")
            write_amount_source(path, batch, payees, {})
            with open(path, encoding="cp932", newline="") as fh:
                rows = list(csv.DictReader(fh))
        # 顧客コードが無い先でも突合キーは必ずある（案A）
        for r in rows:
            self.assertTrue(r["口座自然キー"])
            self.assertEqual(len(r["口座自然キー"].split("-")), 4)

    def test_amounts_match_the_zengin_file(self):
        import csv, tempfile, os
        from zengin.amounts import write_amount_source
        batch, payees = self._batch()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.csv")
            write_amount_source(path, batch, payees, {})
            with open(path, encoding="cp932", newline="") as fh:
                total = sum(int(r["金額"]) for r in csv.DictReader(fh))
        self.assertEqual(total, batch.total_amount)


class TestInvoiceReconciliation(unittest.TestCase):
    """読み取り器が誰であれ、合否は計算が決める。"""

    def real(self, **kw):
        from zengin.reconcile import InvoiceFigures
        # アイティーアイ(株) 2026-07-31 請求明細書 No.1099365 の実数字
        base = dict(previous_billed=592_438, payment_received=592_438,
                    carried_over=0, purchases=342_520, tax=34_252,
                    subtotal=376_772, total_billed=376_772,
                    source_file="test.pdf", read_by="test")
        base.update(kw)
        return InvoiceFigures(**base)

    def test_real_invoice_reconciles(self):
        from zengin.reconcile import accept_or_raise, reconcile
        r = reconcile(self.real())
        self.assertTrue(r.payable, r.failures)
        self.assertEqual(accept_or_raise(self.real()), 376_772)

    def test_misread_total_is_caught(self):
        from zengin.reconcile import accept_or_raise
        with self.assertRaises(ValidationError) as cm:
            accept_or_raise(self.real(total_billed=376_712))
        self.assertIn("今回御請求額", str(cm.exception))

    def test_misread_tax_is_caught(self):
        from zengin.reconcile import reconcile
        r = reconcile(self.real(tax=3_425))
        self.assertFalse(r.payable)

    def test_transposed_digits_in_purchases_is_caught(self):
        # 342,520 -> 342,250 （桁の入れ替わりはOCRの典型的な誤り）
        from zengin.reconcile import reconcile
        self.assertFalse(reconcile(self.real(purchases=342_250)).payable)

    def test_tax_rounding_within_one_yen_is_tolerated(self):
        # 端数処理は業者ごとに違う。±1円は許容する。
        from zengin.reconcile import reconcile
        self.assertTrue(reconcile(self.real(
            purchases=342_521, tax=34_252, subtotal=376_773,
            total_billed=376_773)).payable)

    def test_missing_total_never_passes(self):
        from zengin.reconcile import reconcile
        self.assertFalse(reconcile(self.real(total_billed=None)).payable)

    def test_partial_read_skips_rather_than_guesses(self):
        # 取れなかった項目は「検算できない」であって「合格」ではない。
        from zengin.reconcile import reconcile
        r = reconcile(self.real(previous_billed=None, payment_received=None,
                                carried_over=None))
        self.assertIn("繰越額", r.skipped)
        self.assertNotIn("繰越額", r.checked)

    def test_line_items_total_is_checked_when_present(self):
        from zengin.reconcile import reconcile
        self.assertTrue(reconcile(self.real(line_items_total=342_520)).payable)
        self.assertFalse(reconcile(self.real(line_items_total=342_000)).payable)

    def test_negative_total_is_rejected(self):
        from zengin.reconcile import reconcile
        self.assertFalse(reconcile(self.real(total_billed=-1)).payable)


class TestRegistrationNumber(unittest.TestCase):
    """登録番号はネットなしで真偽を判定でき、マスタ照合の鍵になる。"""

    REAL = "T9310001000026"   # 実物の請求書に印字されていた番号

    def test_real_number_validates_offline(self):
        from zengin.tnumber import is_valid, normalize_tnumber as normalize
        self.assertTrue(is_valid(self.REAL))
        self.assertEqual(normalize(self.REAL), self.REAL)

    def test_check_digit_matches_the_real_number(self):
        from zengin.tnumber import check_digit
        self.assertEqual(check_digit(self.REAL[2:]), int(self.REAL[1]))

    def test_single_digit_misread_is_caught(self):
        from zengin.tnumber import normalize_tnumber as normalize
        for bad in ("T9310001000025", "T9310001000036", "T8310001000026"):
            with self.assertRaises(ValidationError, msg=bad):
                normalize(bad)

    def test_fullwidth_and_separators_normalise(self):
        from zengin.tnumber import normalize_tnumber as normalize
        self.assertEqual(normalize("ｔ9310001000026"), self.REAL)
        self.assertEqual(normalize(" T9310001000026 "), self.REAL)

    def test_wrong_length_is_rejected(self):
        from zengin.tnumber import normalize_tnumber as normalize
        for bad in ("T931000100002", "T93100010000267", "T93100010000A6"):
            with self.assertRaises(ValidationError, msg=bad):
                normalize(bad)

    def test_unknown_number_returns_none_not_a_guess(self):
        # 新規取引先は稀。引けなければ止めて人に回す。部分一致はしない。
        from zengin.tnumber import match
        self.assertIsNone(match("T9310001000026", {}))
        self.assertIsNone(match("not-a-number", {"T9310001000026": "P001"}))

    def test_known_number_resolves_to_payee(self):
        from zengin.tnumber import match
        self.assertEqual(match("t9310001000026", {self.REAL: "P001"}), "P001")

    def test_duplicate_registration_in_master_raises(self):
        from zengin.master import Payee, registration_index
        def mk(pid):
            return Payee(payee_id=pid, display_name=pid, bank_code="0185",
                         bank_name_kana="ｶ", branch_code="201",
                         branch_name_kana="ﾃ", deposit_type="1",
                         account_number="1", payee_name_kana="ｶ)ﾃｽﾄ",
                         fee_borne_by="sender", verified_on=date(2026, 9, 1),
                         verified_by="中村", conversion_notes=[],
                         registration_number=self.REAL)
        with self.assertRaises(ValidationError):
            registration_index({"P001": mk("P001"), "P002": mk("P002")})


class TestCorroborationRequired(unittest.TestCase):
    """「検算できなかった」を「合格」として扱わないこと。

    実物のスキャンをOCRしたとき、7欄のうち3欄しか一致しなかった。
    それでも当初の実装は payable=True を返していた（検算が skipped に
    なるだけで failures が空だったため）。1回しか読めていない金額を
    そのまま振り込むのが最も危ないので、支払額は必ず裏取りを要求する。
    """

    def fig(self, **kw):
        from zengin.reconcile import InvoiceFigures
        base = dict(total_billed=376_772, source_file="t.pdf", read_by="ocr")
        base.update(kw)
        return InvoiceFigures(**base)

    def test_amount_alone_is_not_enough(self):
        from zengin.reconcile import reconcile
        r = reconcile(self.fig())          # 支払額しか読めていない
        self.assertFalse(r.payable)
        self.assertFalse(r.corroborated)
        self.assertTrue(any("裏取り" in f for f in r.failures))

    def test_purchases_plus_tax_corroborates(self):
        from zengin.reconcile import reconcile
        r = reconcile(self.fig(purchases=342_520, tax=34_252))
        self.assertTrue(r.corroborated)
        self.assertTrue(r.payable, r.failures)

    def test_carried_over_path_corroborates(self):
        from zengin.reconcile import reconcile
        r = reconcile(self.fig(carried_over=0, subtotal=376_772))
        self.assertTrue(r.payable, r.failures)

    def test_unread_nonzero_carryover_makes_the_sum_disagree(self):
        # 繰越が読めず、実際には繰越があった場合、買上+税とは一致しないので
        # 裏取りに失敗する（黙って通らない）。
        from zengin.reconcile import reconcile
        r = reconcile(self.fig(total_billed=426_772, purchases=342_520,
                               tax=34_252))
        self.assertFalse(r.payable)

    def test_a_single_wrong_digit_still_fails(self):
        from zengin.reconcile import reconcile
        r = reconcile(self.fig(total_billed=376_779, purchases=342_520,
                               tax=34_252))
        self.assertFalse(r.payable)


class TestOcrConsensus(unittest.TestCase):
    """OCRは1回では信用しない。設定を変えて読み、一致したものだけ採る。"""

    def setUp(self):
        from zengin.ocr import tesseract_available
        if not tesseract_available():
            self.skipTest("tesseract が無い環境のためスキップ")

    def test_disagreement_yields_no_value(self):
        from zengin.ocr import CellRead
        r = CellRead(label="金額", value=None, votes={592_438: 3, 597_438: 1})
        self.assertFalse(r.agreed)
        self.assertIn("割れた", r.why)

    def test_agreement_yields_a_value(self):
        from zengin.ocr import CellRead
        r = CellRead(label="金額", value=376_772, votes={376_772: 4})
        self.assertTrue(r.agreed)
        self.assertEqual(r.why, "一致")

    def test_digit_parser_strips_separators(self):
        from zengin.ocr import _digits
        self.assertEqual(_digits("376,772"), [376772])
        self.assertEqual(_digits("376. 772"), [376772])
        # 罫線を "1" と拾うと 3767721 になる（実際に起きた誤読）。
        # 正しい読みと食い違うので、多数決の段階で弾かれる。
        self.assertNotIn(376772, _digits("376,772 1"))


class TestHistory2SD(unittest.TestCase):
    """平均±2σ だけでは小標本で取りこぼす。中央値+MAD を併走させる。"""

    def h(self, **kw):
        from zengin.history import History
        return History(kw)

    def test_normal_amount_passes(self):
        h = self.h(P=[132_000, 132_000, 131_500, 132_500, 132_000])
        self.assertFalse(h.assess("P", 132_000).needs_review)

    def test_double_amount_is_flagged(self):
        h = self.h(P=[132_000, 132_000, 131_500, 132_500, 132_000])
        self.assertTrue(h.assess("P", 264_000).needs_review)

    def test_mean_sd_alone_would_miss_this_but_mad_catches_it(self):
        # 過去に1回だけ巨額があると σ が膨らみ、平均±2σ は反応しない。
        import statistics
        past = [100_000, 102_000, 98_000, 900_000, 101_000]
        mean, sd = statistics.fmean(past), statistics.stdev(past)
        z = (130_000 - mean) / sd
        self.assertLess(abs(z), 2.0, "前提: 2σ では反応しないこと")
        a = self.h(P=past).assess("P", 130_000)
        self.assertTrue(a.needs_review, "MAD 判定が拾うこと")
        self.assertIn("中央値", a.reasons[0])

    def test_constant_payee_any_change_is_flagged(self):
        h = self.h(P=[88_000, 88_000, 88_000, 88_000])
        self.assertFalse(h.assess("P", 88_000).needs_review)
        self.assertTrue(h.assess("P", 88_500).needs_review)

    def test_new_payee_is_always_flagged(self):
        self.assertTrue(self.h().assess("NEW", 1).needs_review)

    def test_short_history_is_flagged_not_silently_passed(self):
        a = self.h(P=[50_000, 51_000]).assess("P", 52_000)
        self.assertTrue(a.needs_review)
        self.assertIn("履歴が2件", a.reasons[0])

    def test_min_absolute_yen_suppresses_trivial_noise(self):
        h = self.h(P=[100_000, 100_001, 99_999, 100_000])
        self.assertTrue(h.assess("P", 100_050).needs_review)
        self.assertFalse(
            h.assess("P", 100_050, min_absolute_yen=1_000).needs_review)

    def test_append_and_roundtrip(self):
        import tempfile, os
        from zengin.history import History
        h = History()
        for x in (100, 200, 300):
            h.append("P", x)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.json")
            h.save(p)
            self.assertEqual(History.load(p).amounts("P"), [100, 200, 300])

    def test_append_rejects_float(self):
        from zengin.history import History
        with self.assertRaises(TypeError):
            History().append("P", 1.5)

    def test_keep_limits_history_length(self):
        from zengin.history import History
        h = History()
        for i in range(30):
            h.append("P", i, keep=5)
        self.assertEqual(h.amounts("P"), [25, 26, 27, 28, 29])


class TestRapidOcrReader(unittest.TestCase):
    """実物のスキャンで測った結果を退行検知として固定する。

    標本は請求書1通ぶん（7欄）。一般の精度ではないが、
    「前は読めていたものが読めなくなった」は検知できる。
    """

    SAMPLE = "/tmp/claude-0/inv/inv510_p1_0.png"
    BOX = (1195, 710, 1330, 752)      # 今回御請求額
    TRUTH = 376_772

    def setUp(self):
        import os
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except ImportError:
            self.skipTest("rapidocr 未導入のためスキップ")
        if not os.path.exists(self.SAMPLE):
            self.skipTest("実物サンプルが無い環境のためスキップ")

    def test_reads_the_real_amount(self):
        from zengin.readers import RapidOcrReader
        self.assertEqual(RapidOcrReader().read(self.SAMPLE, self.BOX, "金額"),
                         [self.TRUTH])

    def test_low_confidence_is_rejected(self):
        from zengin.readers import RapidOcrReader
        # 確信度の下限を 1.0 にすれば、どんな読みも採用されない
        self.assertEqual(
            RapidOcrReader(min_confidence=1.0).read(self.SAMPLE, self.BOX, "金額"),
            [])

    def test_cross_read_with_tesseract_agrees_on_this_cell(self):
        from zengin.readers import RapidOcrReader, TesseractReader, cross_read
        r = cross_read(self.SAMPLE, self.BOX, "金額",
                       [RapidOcrReader(), TesseractReader()])
        self.assertTrue(r.agreed, r.why)
        self.assertEqual(r.value, self.TRUTH)

    def test_disagreement_yields_nothing(self):
        from zengin.readers import cross_read

        class Always:
            def __init__(self, n, v): self.name, self._v = n, v
            def read(self, *a): return [self._v]

        r = cross_read(self.SAMPLE, self.BOX, "金額",
                       [Always("a", 1), Always("b", 2)])
        self.assertFalse(r.agreed)
        self.assertIn("不一致", r.why)


class TestReaderSelection(unittest.TestCase):
    """RapidOCR を既定にし、VLM は控えとして選べること。"""

    def test_default_is_rapidocr_only(self):
        from zengin.readers import make_readers
        self.assertEqual([r.name for r in make_readers()], ["rapidocr"])

    def test_vlm_is_not_in_the_default(self):
        # 未検証のものを黙って既定に入れない
        from zengin.readers import make_readers
        self.assertNotIn("ollama", [r.name for r in make_readers()])

    def test_backup_preset_pairs_rapidocr_with_vlm(self):
        from zengin.readers import make_readers
        self.assertEqual([r.name for r in make_readers("rapidocr+ollama")],
                         ["rapidocr", "ollama"])

    def test_unknown_preset_raises_with_the_choices(self):
        from zengin.readers import make_readers
        with self.assertRaises(ValidationError) as cm:
            make_readers("gpt")
        self.assertIn("rapidocr", str(cm.exception))

    def test_ollama_model_can_be_overridden(self):
        from zengin.readers import make_readers
        r = make_readers("ollama", ollama_model="qwen2.5vl:7b")[0]
        self.assertEqual(r.model, "qwen2.5vl:7b")


class TestTransferBundle(unittest.TestCase):
    """搬入一式の照合（USB不可・共有フォルダ経由のため）。"""

    def _bundle(self, tmp):
        import subprocess, sys, pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        wheels = pathlib.Path(tmp) / "wh"
        wheels.mkdir()
        (wheels / "x-1.0-py3-none-any.whl").write_bytes(b"dummy wheel")
        out = pathlib.Path(tmp) / "bundle"
        r = subprocess.run(
            [sys.executable, "make_transfer_bundle.py",
             "--wheels", str(wheels), "--out", str(out)],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return out

    def _verify(self, out):
        import subprocess, sys
        return subprocess.run([sys.executable, "verify_transfer.py"],
                              cwd=out, capture_output=True, text=True)

    def test_clean_bundle_verifies(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r = self._verify(self._bundle(tmp))
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("すべて一致", r.stdout)

    def test_truncated_file_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = self._bundle(tmp)
            p = out / "mirai_keiri.py"
            p.write_bytes(p.read_bytes()[:-50])
            r = self._verify(out)
            self.assertEqual(r.returncode, 1)
            self.assertIn("install しないこと", r.stdout)

    def test_missing_file_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = self._bundle(tmp)
            (out / "mirai_keiri.py").unlink()
            r = self._verify(out)
            self.assertEqual(r.returncode, 1)
            self.assertIn("見つかりません", r.stdout)

    def test_unexpected_extra_file_is_reported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = self._bundle(tmp)
            (out / "なぞのファイル.exe").write_text("x")
            r = self._verify(out)
            self.assertIn("一覧にないファイル", r.stdout)

    def test_missing_manifest_refuses(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = self._bundle(tmp)
            (out / "MANIFEST.sha256").unlink()
            self.assertEqual(self._verify(out).returncode, 2)


class TestTemplates(unittest.TestCase):
    """業者ごとの欄の位置を外部ファイルで持つ。座標は解像度差を吸収する。"""

    def tpl(self, **kw):
        from zengin.templates import Template
        base = dict(template_id="t1", display_name="テスト",
                    reference_size=(1654, 2340),
                    fields={"今回御請求額": (1195, 710, 1330, 752)},
                    required_fields=["今回御請求額"],
                    registration_number="T9310001000026")
        base.update(kw)
        return Template(**base)

    def test_same_size_returns_boxes_unchanged(self):
        t = self.tpl()
        self.assertEqual(t.boxes_for((1654, 2340))["今回御請求額"],
                         (1195, 710, 1330, 752))

    def test_boxes_scale_with_the_image(self):
        t = self.tpl()
        x0, y0, x1, y1 = t.boxes_for((3308, 4680))["今回御請求額"]
        self.assertEqual((x0, y0, x1, y1), (2390, 1420, 2660, 1504))

    def test_different_aspect_ratio_refuses(self):
        # 向きや様式が違う画像で、黙って別の場所を読まないこと
        with self.assertRaises(ValidationError) as cm:
            self.tpl().boxes_for((1654, 1200))
        self.assertIn("縦横比", str(cm.exception))

    def test_box_outside_reference_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.tpl(fields={"x": (0, 0, 9999, 100)}).validate()

    def test_required_field_must_exist(self):
        with self.assertRaises(ValidationError):
            self.tpl(required_fields=["無い欄"]).validate()

    def test_template_without_any_key_is_rejected(self):
        # 引けないテンプレートは使えない
        with self.assertRaises(ValidationError):
            self.tpl(registration_number="", payee_id="").validate()

    def test_lookup_normalises_the_registration_number(self):
        from zengin.templates import TemplateSet
        ts = TemplateSet([self.tpl()])
        self.assertIsNotNone(ts.find(registration_number="t9310001000026"))

    def test_unknown_number_returns_none(self):
        from zengin.templates import TemplateSet
        ts = TemplateSet([self.tpl()])
        self.assertIsNone(ts.find(registration_number="T6120001000015"))
        self.assertIsNone(ts.find(registration_number="ごみ"))

    def test_duplicate_registration_number_raises(self):
        from zengin.templates import TemplateSet
        with self.assertRaises(ValidationError):
            TemplateSet([self.tpl(template_id="a"), self.tpl(template_id="b")])

    def test_duplicate_template_id_raises(self):
        from zengin.templates import TemplateSet
        with self.assertRaises(ValidationError):
            TemplateSet([self.tpl(), self.tpl(registration_number="",
                                              payee_id="P1")])

    def test_unverified_template_is_visible_as_such(self):
        self.assertFalse(self.tpl().is_verified)
        self.assertTrue(self.tpl(verified_on="2026-09-25",
                                 verified_by="中村").is_verified)

    def test_sample_file_loads(self):
        from zengin.templates import load_templates
        ts = load_templates("data/templates/invoice_templates.sample.json")
        self.assertGreaterEqual(len(ts), 1)

    def test_bad_version_is_rejected(self):
        import json, tempfile, os
        from zengin.templates import load_templates
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump({"version": 2, "templates": []}, fh)
            p = fh.name
        try:
            with self.assertRaises(ValidationError):
                load_templates(p)
        finally:
            os.unlink(p)

    def test_missing_file_is_rejected(self):
        from zengin.templates import load_templates
        with self.assertRaises(ValidationError):
            load_templates("/nonexistent/templates.json")
