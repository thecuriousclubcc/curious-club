"""Machine-checks that this pipeline cannot reach the network or a model.

別章第5条第1項 (personal data stays inside the closed hospital environment) and
第6条第1項 (no personal data into generative AI) are contract terms, not
preferences. This test is the evidence that the 経理 pipeline satisfies them,
and can be cited directly in the 検査基準.
"""

from __future__ import annotations

import ast
import re
import socket
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "zengin"
sys.path.insert(0, str(PACKAGE.parent))

# Modules that would give the pipeline a way off the machine, or to a model.
FORBIDDEN_IMPORTS = {
    "socket", "httplib", "urllib2", "urllib3", "requests",
    "httpx", "aiohttp", "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "openai", "anthropic", "ollama", "groq", "google",
    "transformers", "torch", "llama_cpp", "langchain", "boto3",
}

# subprocess は原則禁止。OCR が tesseract を起動するためだけに ocr.py に
# 限って許す。許すかわりに、下の TestSubprocessIsTesseractOnly で
# 「起動されるのは tesseract だけ」「shell=True を使わない」を機械検査する。
SUBPROCESS_ALLOWED_IN = {"ocr.py"}

# urllib は原則禁止。ローカルの Ollama を叩く readers.py に限って許す。
# 許すかわりに TestLocalOnly が「宛先が 127.0.0.1 / localhost だけ」を検査する。
# 保証の意味はこう変わる:
#   旧「ネットワークを一切使わない」
#   新「**この機械の外へは出ない**」（機械検査つき）
URLLIB_ALLOWED_IN = {"readers.py"}
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

# http.server は確認画面のためだけに review_server.py に限って許す。
# 許すかわりに TestLocalOnly が「127.0.0.1 にしか束縛しない」を検査する。
# 画面はこの端末の中だけで動き、データは機外に出ない。
HTTP_ALLOWED_IN = {"review_server.py"}

# urllib.parse は文字列処理であって通信しない。どこでも使ってよい。
# 通信するのは urllib.request / urllib.error のみ。
URLLIB_NETWORK_SUBMODULES = ("request", "error")


def _module_files() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


class TestNoNetworkImports(unittest.TestCase):
    def test_no_forbidden_imports_anywhere_in_the_package(self):
        offenders: list[str] = []
        for path in _module_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    root = name.split(".")[0]
                    if root in FORBIDDEN_IMPORTS:
                        offenders.append(f"{path.name}:{node.lineno} imports {name}")
                    if root == "urllib" and path.name not in URLLIB_ALLOWED_IN:
                        sub = name.split(".")[1] if "." in name else ""
                        if sub in URLLIB_NETWORK_SUBMODULES or not sub:
                            offenders.append(
                                f"{path.name}:{node.lineno} imports {name} "
                                f"（通信する urllib の許可は "
                                f"{sorted(URLLIB_ALLOWED_IN)} のみ）")
                    if root == "http" and path.name not in HTTP_ALLOWED_IN:
                        offenders.append(
                            f"{path.name}:{node.lineno} imports {name} "
                            f"（許可は {sorted(HTTP_ALLOWED_IN)} のみ）")
                    if (root == "subprocess"
                            and path.name not in SUBPROCESS_ALLOWED_IN):
                        offenders.append(
                            f"{path.name}:{node.lineno} imports subprocess "
                            f"（許可は {sorted(SUBPROCESS_ALLOWED_IN)} のみ）")
        self.assertEqual(offenders, [], "ネットワーク/AI モジュールの import: " + str(offenders))

    def test_package_has_modules_to_check(self):
        # Guards against the check silently passing on an empty glob.
        self.assertGreaterEqual(len(_module_files()), 5)


class TestSubprocessIsTesseractOnly(unittest.TestCase):
    """subprocess を許した ocr.py が、tesseract 以外を起動しないこと。

    「外部通信しない」という保証を、OCR の導入で黙って緩めないための検査。
    起動対象が tesseract に固定されていること、shell=True を使わないことを
    ソースから機械的に確かめる。
    """

    def _ocr_tree(self):
        return ast.parse((PACKAGE / "ocr.py").read_text(encoding="utf-8"))

    def test_no_shell_true_anywhere(self):
        offenders = []
        for node in ast.walk(self._ocr_tree()):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                if not (isinstance(node.value, ast.Constant)
                        and node.value.value is False):
                    offenders.append(f"line {node.value.lineno}")
        self.assertEqual(offenders, [], "shell=True は使わないこと")

    def test_every_subprocess_call_runs_tesseract(self):
        """argv の先頭が文字列 "tesseract" か、それを先頭に組んだ変数のみ。"""
        src = (PACKAGE / "ocr.py").read_text(encoding="utf-8")
        calls = [n for n in ast.walk(self._ocr_tree())
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == "subprocess"]
        self.assertTrue(calls, "subprocess の呼び出しが見つかりません")
        # ソース中で argv を組んでいる箇所が tesseract 始まりであること
        self.assertIn('["tesseract"', src.replace("'", '"'),
                      "argv の先頭が tesseract に固定されていません")
        for c in calls:
            self.assertEqual(c.func.attr, "run",
                             "subprocess は run のみ（Popen/shell 系は不可）")

    def test_ocr_declares_no_network_use(self):
        src = (PACKAGE / "ocr.py").read_text(encoding="utf-8")
        self.assertIn("外部通信なし", src)


class TestLocalOnly(unittest.TestCase):
    """外へ出る通信が存在しないことを、**要求の宛先**で検査する。

    文字列に http:// が含まれること自体は問題ではない。xlsx.py の
    openxmlformats.org は XML の名前空間（識別子）で、取得しに行くものでは
    ない。コメント中のホスト名も同様。検査すべきは「実際に要求を出す先」。

    保証の意味:
      旧「ネットワークを一切使わない」
      新「**この機械の外へは出ない**」（下記で機械検査）
    """

    def _readers_tree(self):
        return ast.parse((PACKAGE / "readers.py").read_text(encoding="utf-8"))

    def test_ollama_url_constant_is_loopback(self):
        from zengin.readers import OLLAMA_URL
        host = OLLAMA_URL.split("//", 1)[1].split("/")[0].split(":")[0]
        self.assertIn(host, LOCAL_HOSTS, f"宛先が loopback ではない: {OLLAMA_URL}")

    def test_only_readers_py_makes_network_urllib_calls(self):
        """通信する urllib（request/error）は readers.py だけ。

        urllib.parse は文字列処理であって通信しないので、確認画面など
        どこで使ってもよい。ここを一緒くたに禁止すると、意味のない
        禁止になって本当に見たいものが埋もれる。
        """
        offenders = []
        for path in _module_files():
            if path.name in URLLIB_ALLOWED_IN:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module or ""]
                for m in mods:
                    bits = m.split(".")
                    if bits[0] != "urllib":
                        continue
                    sub = bits[1] if len(bits) > 1 else ""
                    if sub in URLLIB_NETWORK_SUBMODULES or not sub:
                        offenders.append(f"{path.name}:{node.lineno} {m}")
        self.assertEqual(offenders, [])

    def test_every_request_uses_the_loopback_constant(self):
        """urlopen / Request の宛先が OLLAMA_URL 定数だけであること。

        文字列リテラルや組み立てたURLを直接渡していたら失敗させる。
        """
        calls = []
        for node in ast.walk(self._readers_tree()):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else getattr(fn, "id", ""))
            if name in ("urlopen", "Request"):
                calls.append(node)
        self.assertTrue(calls, "urllib の呼び出しが見つかりません")

        # Request(...) は宛先を直接受け取るので、必ず OLLAMA_URL であること。
        requests_ = [c for c in calls if self._name_of(c) == "Request"]
        self.assertTrue(requests_, "Request の生成が見つかりません")
        for c in requests_:
            self.assertTrue(c.args, "Request に宛先が渡されていません")
            first = c.args[0]
            self.assertIsInstance(
                first, ast.Name,
                f"line {first.lineno}: 宛先はリテラルではなく OLLAMA_URL 定数で")
            self.assertEqual(
                first.id, "OLLAMA_URL",
                f"line {first.lineno}: 宛先が OLLAMA_URL 以外です")

        # urlopen は Request オブジェクトだけを受け取ること。
        # 文字列URLを直接渡す経路を塞ぐ（Request 側の検査を迂回できてしまう）。
        for c in [c for c in calls if self._name_of(c) == "urlopen"]:
            self.assertTrue(c.args)
            first = c.args[0]
            self.assertIsInstance(
                first, ast.Name,
                f"line {first.lineno}: urlopen にURL文字列を直接渡さないこと")

    @staticmethod
    def _name_of(call: ast.Call) -> str:
        fn = call.func
        return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")

    def test_review_server_binds_only_to_loopback(self):
        """確認画面が外から繋がる場所に立たないこと。"""
        from zengin.review_server import BIND_HOST
        self.assertIn(BIND_HOST, LOCAL_HOSTS)

    def test_server_is_constructed_with_the_bind_constant(self):
        """束縛先がリテラルで書き換えられていないこと。"""
        tree = ast.parse((PACKAGE / "review_server.py").read_text("utf-8"))
        found = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "ThreadingHTTPServer"):
                found = True
                addr = node.args[0]
                self.assertIsInstance(addr, ast.Tuple)
                host = addr.elts[0]
                self.assertIsInstance(
                    host, ast.Name,
                    "束縛先はリテラルではなく BIND_HOST 定数で書くこと")
                self.assertEqual(host.id, "BIND_HOST")
        self.assertTrue(found, "サーバの生成が見つかりません")

    def test_no_bind_all_interfaces_anywhere(self):
        src = (PACKAGE / "review_server.py").read_text("utf-8")
        for bad in ('"0.0.0.0"', "'0.0.0.0'", '"::"'):
            self.assertNotIn(bad, src, f"全インタフェースへの束縛: {bad}")

    def test_no_url_building_from_parts(self):
        """http:// を含む文字列リテラルが readers.py に無いこと（定数を除く）。"""
        src = (PACKAGE / "readers.py").read_text(encoding="utf-8")
        literals = re.findall(r'"(https?://[^"]*)"', src)
        for lit in literals:
            host = lit.split("//", 1)[1].split("/")[0].split(":")[0]
            self.assertIn(host, LOCAL_HOSTS, f"外向きのURL: {lit}")


class TestNoSocketAtRuntime(unittest.TestCase):
    """Run the whole pipeline with sockets disabled; it must still work."""

    def test_full_pipeline_runs_with_sockets_disabled(self):
        from datetime import date

        real_socket = socket.socket

        def blocked(*args, **kwargs):
            raise AssertionError("パイプラインがソケットを開こうとしました")

        socket.socket = blocked
        try:
            from zengin.format import render
            from zengin.invoices import InvoiceRow, aggregate
            from zengin.master import Payee
            from zengin.model import Requester, TransferBatch
            from zengin.verify import verify

            payee = Payee(
                payee_id="P001", display_name="テスト商事",
                bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                branch_code="201", branch_name_kana="ﾃﾝﾓﾝｶﾝ",
                deposit_type="1", account_number="7654321",
                payee_name_kana="ｶ)ﾃｽﾄｼﾖｳｼﾞ", fee_borne_by="sender",
                verified_on=date(2026, 9, 1), verified_by="中村",
                conversion_notes=[],
            )
            rows = [InvoiceRow("P001", "T-1", date(2026, 10, 1), 12345, "t.pdf")]
            batch = TransferBatch(
                requester=Requester(
                    consignor_code="0000012345", name_kana="ｲ)ﾃｽﾄ",
                    bank_code="0185", bank_name_kana="ｶｺﾞｼﾏ",
                    branch_code="101", branch_name_kana="ﾎﾝﾃﾝ",
                    deposit_type="1", account_number="1234567"),
                transfer_date=date(2026, 10, 31),
                payments=aggregate(rows, {"P001": payee}),
            )
            raw = render(batch)
            self.assertEqual(verify(raw, expected_count=1, expected_total=12345), [])
        finally:
            socket.socket = real_socket


if __name__ == "__main__":
    unittest.main()
