"""単一ファイル版が壊れていないことを検査する。

現場へ持っていくのはこのファイルなので、パッケージ側だけ通っても意味がない。
実際に tnumber.py の取りこぼしで NameError を出したため、機械検査にした。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestSingleFileBundle(unittest.TestCase):

    def test_order_covers_every_module(self):
        sys.path.insert(0, str(ROOT))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bsf", ROOT / "build_single_file.py")
        bsf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bsf)
        on_disk = {p.stem for p in (ROOT / "zengin").glob("*.py")
                   if p.stem != "__init__"}
        self.assertEqual(set(bsf.ORDER), on_disk,
                         "ORDER とパッケージの中身が食い違っています")

    def test_bundle_builds_and_selftest_passes(self):
        build = subprocess.run(
            [sys.executable, "build_single_file.py"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(build.returncode, 0,
                         f"バンドルに失敗: {build.stdout}{build.stderr}")

        out = subprocess.run(
            [sys.executable, "dist/mirai_keiri.py", "--selftest"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0,
                         f"セルフテストが失敗: {out.stdout}{out.stderr}")
        self.assertIn("0 件失敗", out.stdout)

    def test_bundle_runs_the_full_pipeline(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run(
                [sys.executable, "dist/mirai_keiri.py",
                 "--master", "data/payees.sample.csv",
                 "--invoices", "data/invoices.sample.csv",
                 "--config", "data/requester.sample.json",
                 "--date", "2026-10-31", "--out", d],
                cwd=ROOT, capture_output=True, text=True)
            # サンプル設定は未確定値なので、止まるのが正しい挙動。
            # 「黙って進まない」ことと、理由が読めることを確かめる。
            both = out.stdout + out.stderr
            self.assertNotEqual(out.returncode, 0, "未確定の設定で進んでいます")
            self.assertIn("エラー", both)
            self.assertTrue(len(both.strip()) > 20, "理由が示されていません")

    def test_bundle_has_no_intra_package_imports_left(self):
        src = (ROOT / "dist" / "mirai_keiri.py").read_text(encoding="utf-8")
        self.assertNotIn("from .", src,
                         "パッケージ内 import が残っています（実行時に失敗する）")


if __name__ == "__main__":
    unittest.main()
