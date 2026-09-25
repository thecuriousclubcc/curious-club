"""PDFを請求書の単位に切り分け、業者を特定する。

**1ファイル＝1請求書ではない。** 実物では24ページのPDFに少なくとも4業者の
請求書が入っていた。業者ごとに様式も項目名も違う（「請求明細書」と「請求書」、
表の位置も別）。1ページ目だけ見る前提では動かない。

■ 様式を知る前に業者を特定する
適格請求書発行事業者登録番号（T+13桁）は、インボイス制度により
**どの様式の請求書にも必ず印字される**。様式がバラバラでも、ここだけは共通。
しかも法人番号の検査用数字で**その場で真偽を判定できる**ので、
読み間違いをそのまま業者特定に使ってしまう事故が起きない。

実測（実物24ページ）: 0.94〜0.98 の確信度で検出。ハイフン区切り
（T7-3200-0100-0415）でも正規化して一致した。

■ ページのまとめ方
    登録番号あり → その業者の請求書が始まる（or 続く）
    登録番号なし → 直前の請求書の続きのページ

**限界:** 同じ業者の請求書が2通続くと、この規則だけでは切れ目が分からない。
その場合は「切れ目が判断できない」として人に回す。黙って1通に混ぜない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .model import ValidationError
from .tnumber import normalize_tnumber

# T + 13桁。間にハイフン・空白が入りうる（実物にあり）
TNUMBER_PATTERN = re.compile(r"[TtＴ][\s\-‐－ー]*[\d\s\-‐－]{13,22}")

# 「請求書が始まる」ことを示す語。同一業者の連続を切る手がかり
INVOICE_TITLES = ("請求書", "請求明細書", "御請求書", "ご請求書", "INVOICE")


@dataclass
class Page:
    index: int                       # 1始まり
    image_path: str
    registration_number: str = ""    # 正規化済み。見つからなければ空
    confidence: float = 0.0
    looks_like_first_page: bool = False
    raw_text: str = ""


@dataclass
class InvoiceDoc:
    """請求書1通ぶん。1ページとは限らない。"""

    registration_number: str
    pages: list[Page] = field(default_factory=list)
    ambiguous: bool = False          # 切れ目が判断できない
    reason: str = ""

    @property
    def page_numbers(self) -> list[int]:
        return [p.index for p in self.pages]

    @property
    def first_page(self) -> Page:
        return self.pages[0]


def pdf_to_pages(pdf_path: str | Path, out_dir: str | Path) -> list[str]:
    """PDFの各ページを画像として書き出す。

    スキャンされたPDFは1ページ＝1画像なので、そのまま取り出す。
    取り出せないページは、そのページだけ飛ばさずエラーにする
    （黙って抜けると請求書が1通まるごと消える）。
    """
    try:
        import pypdf
    except ImportError as e:
        raise ValidationError(
            "pypdf が入っていません。搬入一式に含めてください。") from e

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reader = pypdf.PdfReader(str(pdf_path))
    stem = Path(pdf_path).stem
    paths: list[str] = []

    for i, page in enumerate(reader.pages, 1):
        images = list(page.images)
        if not images:
            raise ValidationError(
                f"{pdf_path} の {i}ページ目から画像を取り出せません。"
                f"スキャン画像のPDFを想定しています。")
        p = out / f"{stem}_p{i:03d}.png"
        images[0].image.save(p)
        paths.append(str(p))
    return paths


def find_registration_number(image_path: str, ocr=None) -> tuple[str, float, str]:
    """ページから登録番号を探す。検査用数字が合うものだけ返す。

    戻り値: (正規化済み番号, 確信度, 読み取った生テキスト)
    見つからなければ ("", 0.0, "")
    """
    import numpy as np
    from PIL import Image

    if ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise ValidationError(
                "rapidocr-onnxruntime が入っていません。") from e
        ocr = RapidOCR()

    res, _ = ocr(np.array(Image.open(image_path).convert("RGB")))
    best: tuple[str, float, str] = ("", 0.0, "")
    for r in (res or []):
        text, conf = str(r[1]), float(r[2])
        for m in TNUMBER_PATTERN.finditer(text):
            try:
                n = normalize_tnumber(m.group())
            except ValidationError:
                continue          # 検査用数字が合わない＝読み違い。使わない
            if conf > best[1]:
                best = (n, conf, text.strip())
    return best


def scan_pages(image_paths: list[str], ocr=None) -> list[Page]:
    pages: list[Page] = []
    for i, path in enumerate(image_paths, 1):
        n, conf, raw = find_registration_number(path, ocr)
        pages.append(Page(index=i, image_path=path, registration_number=n,
                          confidence=conf, raw_text=raw,
                          looks_like_first_page=any(t in raw for t in INVOICE_TITLES)))
    return pages


def group_into_invoices(pages: list[Page]) -> list[InvoiceDoc]:
    """ページを請求書の単位にまとめる。

    同一業者の請求書が続く場合、規則だけでは切れ目が決まらない。
    そのときは ambiguous を立てて人に回す（黙って1通に混ぜない）。
    """
    docs: list[InvoiceDoc] = []
    for p in pages:
        if not p.registration_number:
            if docs:
                docs[-1].pages.append(p)          # 続きのページ
            else:
                docs.append(InvoiceDoc(
                    registration_number="", pages=[p], ambiguous=True,
                    reason="先頭のページに登録番号が見つかりません"))
            continue

        if docs and docs[-1].registration_number == p.registration_number:
            prev = docs[-1]
            prev.pages.append(p)
            # 同じ業者で、かつ「請求書」らしい見出しが再び出た＝別の請求書かも
            if p.looks_like_first_page:
                prev.ambiguous = True
                prev.reason = (
                    f"同じ業者のページが続いており、{p.index}ページ目にも"
                    f"請求書の見出しがあります。1通か2通か判断できません。")
            continue

        docs.append(InvoiceDoc(registration_number=p.registration_number,
                               pages=[p]))
    return docs


def summarise(docs: list[InvoiceDoc]) -> list[str]:
    lines = [f"請求書 {len(docs)}通 に分かれました"]
    for i, d in enumerate(docs, 1):
        mark = " ⚠要確認" if d.ambiguous else ""
        num = d.registration_number or "（登録番号なし）"
        lines.append(f"  {i:>2}. {num}  ページ {d.page_numbers}{mark}")
        if d.ambiguous:
            lines.append(f"      → {d.reason}")
    return lines
