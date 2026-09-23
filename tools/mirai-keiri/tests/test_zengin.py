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
        from zengin.custcode import normalize
        self.assertEqual(normalize("9387"), "0000009387")

    def test_already_ten_digits_is_unchanged(self):
        from zengin.custcode import normalize
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
        from zengin.custcode import normalize
        with self.assertRaises(ValidationError):
            normalize("A123")

    def test_overlong_code_raises(self):
        from zengin.custcode import normalize
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
