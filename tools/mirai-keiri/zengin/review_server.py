"""確認画面（この端末の中だけで動く簡易サーバ）。

127.0.0.1 に束縛する。外からは繋がらない。標準ライブラリだけで動くので、
院内に追加で入れるものは無い。

画面の考え方:
  - 開いた瞬間に「確認待ち N件」か「確認待ちなし」が分かる
  - 1件ずつ、請求書の該当箇所の画像を見ながら金額を入れる
  - 入れた金額も自動と同じ検算を通る。おかしければその場で赤く出る
  - 全部片付くまで銀行用ファイルは作られない（画面にもそう書く）
"""

from __future__ import annotations

import html
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .model import ValidationError
from .review import ReviewQueue

BIND_HOST = "127.0.0.1"          # ここ以外に束縛しない（テストで検査）
DEFAULT_PORT = 8765

_CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;font-family:"Yu Gothic","Hiragino Sans",system-ui,sans-serif;
     background:#f5f5f3;color:#1a1a1a;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:#555;margin:0 0 24px;font-size:14px}
.banner{padding:16px 20px;border-radius:10px;margin-bottom:24px;font-size:17px;
        font-weight:700}
.wait{background:#fff4e5;border:2px solid #e8944a;color:#8a4b00}
.clear{background:#eaf6ec;border:2px solid #4a9a5e;color:#1d5c2e}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:20px;
      margin-bottom:20px}
.name{font-size:19px;font-weight:700;margin:0 0 2px}
.why{display:inline-block;background:#fdeaea;color:#8a1f1f;border-radius:6px;
     padding:4px 10px;font-size:14px;font-weight:700;margin:8px 0}
.detail{color:#666;font-size:13px;margin:4px 0 12px;word-break:break-all}
img.crop{max-width:100%;border:1px solid #ccc;border-radius:6px;background:#fff;
         display:block;margin:12px 0}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-top:12px}
label{display:block;font-size:13px;color:#444;margin-bottom:4px}
input[type=text]{font-size:18px;padding:10px 12px;border:2px solid #bbb;
                 border-radius:6px;width:200px;font-family:inherit}
input.who{width:160px;font-size:15px}
button{font-size:16px;font-weight:700;padding:11px 22px;border:0;border-radius:6px;
       background:#1a5fb4;color:#fff;cursor:pointer;font-family:inherit}
button:hover{background:#174f96}
.done{color:#1d5c2e;font-weight:700}
.note{background:#f0f0ee;border-left:4px solid #999;padding:12px 16px;
      font-size:14px;color:#444;margin:24px 0}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}
td,th{border-bottom:1px solid #eee;padding:7px 6px;text-align:left}
th{color:#666;font-weight:600}
.amt{text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:480px){input[type=text]{width:100%}}
"""


def _page(queue: ReviewQueue, message: str = "", error: str = "") -> str:
    pend = queue.pending()
    done = queue.resolved()
    parts = [f"<!doctype html><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>振込の確認</title><style>{_CSS}</style>"
             f"<div class='wrap'><h1>振込の確認</h1>"
             f"<p class='sub'>この画面はこのパソコンの中だけで動いています。"
             f"外には何も出ません。</p>"]

    if pend:
        parts.append(f"<div class='banner wait'>あなたの確認待ち "
                     f"{len(pend)}件<br>"
                     f"<span style='font-weight:400;font-size:15px'>"
                     f"すべて片付くまで、銀行に出すファイルは作られません。</span>"
                     f"</div>")
    else:
        parts.append(f"<div class='banner clear'>確認待ちなし"
                     f"{f'（{len(done)}件すべて確認済み）' if done else ''}<br>"
                     f"<span style='font-weight:400;font-size:15px'>"
                     f"銀行に出すファイルを作れます。</span></div>")

    if error:
        parts.append(f"<div class='banner wait'>{html.escape(error)}</div>")
    if message:
        parts.append(f"<div class='banner clear'>{html.escape(message)}</div>")

    for it in pend:
        name = html.escape(it.display_name or it.payee_id)
        prop = (f"{it.proposed_amount:,} 円" if it.proposed_amount is not None
                else "読み取れませんでした")
        parts.append(
            f"<div class='card'><p class='name'>{name}</p>"
            f"<div class='why'>{html.escape(it.reason)}</div>")
        if it.detail:
            parts.append(f"<p class='detail'>{html.escape(it.detail)}</p>")
        if it.crop:
            parts.append(f"<img class='crop' src='/crop/{it.item_id}' "
                         f"alt='請求書の該当箇所'>")
        parts.append(
            f"<table><tr><th>機械が読んだ金額</th>"
            f"<td class='amt'>{prop}</td></tr></table>"
            f"<form method='post' action='/resolve'>"
            f"<input type='hidden' name='item_id' value='{html.escape(it.item_id)}'>"
            f"<div class='row'>"
            f"<div><label>正しい金額（円・半角数字）</label>"
            f"<input type='text' name='amount' inputmode='numeric' required></div>"
            f"<div><label>入力した人</label>"
            f"<input type='text' class='who' name='who' required></div>"
            f"<button type='submit'>確定する</button></div></form></div>")

    if done:
        parts.append("<div class='card'><p class='name'>確認済み</p><table>"
                     "<tr><th>支払先</th><th class='amt'>金額</th>"
                     "<th>手を入れた記録</th></tr>")
        for it in done:
            parts.append(
                f"<tr><td>{html.escape(it.display_name or it.payee_id)}</td>"
                f"<td class='amt'>{it.figures.total_billed:,} 円</td>"
                f"<td class='done'>"
                f"{html.escape(it.override.describe()) if it.override else '自動'}"
                f"</td></tr>")
        parts.append("</table></div>")

    parts.append(
        "<div class='note'>入れた金額も、機械が読んだ金額とまったく同じ"
        "計算の確認を通ります。請求書の中で計算が合わない金額は、"
        "手で入れても確定しません。</div></div>")
    return "".join(parts)


def make_handler(queue: ReviewQueue):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):        # 画面を汚さない
            pass

        def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, text: str, status: int = 200) -> None:
            self._send(text.encode("utf-8"), "text/html; charset=utf-8", status)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                q = parse_qs(urlparse(self.path).query)
                self._html(_page(queue, q.get("msg", [""])[0],
                                 q.get("err", [""])[0]))
            elif path == "/status.json":
                body = json.dumps(
                    {"pending": len(queue.pending()),
                     "resolved": len(queue.resolved()),
                     "can_output": queue.is_clear},
                    ensure_ascii=False).encode("utf-8")
                self._send(body, "application/json; charset=utf-8")
            elif path.startswith("/crop/"):
                self._crop(path[len("/crop/"):])
            else:
                self._html("<p>ページがありません</p>", 404)

        def _crop(self, item_id: str) -> None:
            items = {i.item_id: i for i in queue.all()}
            it = items.get(item_id)
            if it is None or not it.crop or not it.image_path:
                self._send(b"", "image/png", 404)
                return
            try:
                from PIL import Image
                buf = io.BytesIO()
                Image.open(it.image_path).crop(it.crop).save(buf, format="PNG")
                self._send(buf.getvalue(), "image/png")
            except Exception:
                self._send(b"", "image/png", 404)

        def do_POST(self):
            if urlparse(self.path).path != "/resolve":
                self._html("<p>ページがありません</p>", 404)
                return
            n = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(n).decode("utf-8"))
            item_id = form.get("item_id", [""])[0]
            who = form.get("who", [""])[0]
            raw = form.get("amount", [""])[0].strip().replace(",", "")
            raw = raw.replace("，", "").replace("円", "")

            msg = err = ""
            try:
                if not raw.isdigit():
                    raise ValidationError("金額は半角数字で入れてください")
                item = queue.resolve(item_id, int(raw), who=who)
                if item.resolved:
                    msg = f"{item.display_name or item.payee_id} を確定しました"
                else:
                    err = f"確定できません: {item.reason}"
            except ValidationError as e:
                err = str(e)

            from urllib.parse import urlencode
            self.send_response(303)
            self.send_header("Location", "/?" + urlencode({"msg": msg,
                                                           "err": err}))
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def serve(queue: ReviewQueue, port: int = DEFAULT_PORT):
    """この端末の中だけで確認画面を出す。"""
    server = ThreadingHTTPServer((BIND_HOST, port), make_handler(queue))
    print(f"確認画面: http://{BIND_HOST}:{server.server_address[1]}/")
    print("このパソコンの中だけで動いています。外からは繋がりません。")
    print("終わるときは Ctrl+C を押してください。")
    return server
