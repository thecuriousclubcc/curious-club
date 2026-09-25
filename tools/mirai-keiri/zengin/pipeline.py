"""請求書PDFのフォルダから、確認待ちと出力までを通す。

    PDF群 → 請求書ごとに分割 → 業者を特定 → 金額を読む → 検算 → 2σ
        → 確認待ちが残る？
             はい → 確認画面へ。**銀行用ファイルは作らない**
             いいえ → 振込一覧表 + 銀行用ファイル

個々の部品（intake / templates / readers / reconcile / history / review）は
それぞれ単体で検証済み。ここはそれらを繋ぐだけで、判断は足さない。
**関門を飛ばす経路をここにも作らない。**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .history import History
from .intake import (InvoiceDoc, group_into_invoices, pdf_to_pages, scan_pages)
from .master import Payee, registration_index
from .model import Payment, ValidationError
from .reconcile import InvoiceFigures, reconcile
from .readers import cross_read, make_readers
from .review import (AMBIGUOUS_SPLIT, NO_CORROBORATION, OUTLIER,
                     RECONCILE_FAILED, ReviewItem, ReviewQueue, UNKNOWN_PAYEE,
                     UNREADABLE)
from .templates import TemplateSet

TEMPLATE_MISSING = "この業者の請求書の見方がまだ登録されていません"


@dataclass
class Resolved:
    """機械だけで確定した1件。"""

    payee_id: str
    display_name: str
    amount: int
    registration_number: str
    pages: list[int] = field(default_factory=list)
    source: str = ""


@dataclass
class Result:
    resolved: list[Resolved] = field(default_factory=list)
    queue: ReviewQueue = field(default_factory=ReviewQueue)
    invoices_seen: int = 0

    @property
    def can_output(self) -> bool:
        return self.queue.is_clear

    def lines(self) -> list[str]:
        out = [f"請求書 {self.invoices_seen}通 を読みました",
               f"  自動で確定 {len(self.resolved)}件",
               f"  {self.queue.summary()}"]
        if not self.can_output:
            out.append("  → 確認が済むまで銀行用ファイルは作りません")
        return out


def _read_invoice(doc: InvoiceDoc, templates: TemplateSet, preset: str):
    """1通ぶん読む。戻り値は (figures, 使ったテンプレート, 失敗理由)。"""
    from PIL import Image

    tpl = templates.find(registration_number=doc.registration_number)
    if tpl is None:
        return None, None, TEMPLATE_MISSING

    page = doc.pages[min(tpl.page, len(doc.pages)) - 1]
    try:
        boxes = tpl.boxes_for(Image.open(page.image_path).size)
    except ValidationError as e:
        return None, tpl, str(e)

    readers = make_readers(preset)
    values = {name: cross_read(page.image_path, box, name, readers).value
              for name, box in boxes.items()}
    g = values.get
    fig = InvoiceFigures(
        previous_billed=g("前回御請求額"), payment_received=g("御入金額"),
        carried_over=g("繰越額"), purchases=g("今回御買上額"),
        tax=g("今回消費税額"), subtotal=g("今回合計金額"),
        total_billed=g("今回御請求額"),
        source_file=Path(page.image_path).name, read_by=preset)
    return fig, tpl, ""


def process(pdf_paths: list[str | Path], *, templates: TemplateSet,
            payees: dict[str, Payee], history: History | None = None,
            work_dir: str | Path = "work", preset: str = "rapidocr",
            ocr=None) -> Result:
    """PDFのフォルダを読み、確定分と確認待ちに振り分ける。"""
    history = history or History()
    by_reg = registration_index(payees)
    result = Result(queue=ReviewQueue(history=history))
    work = Path(work_dir)

    for pdf in pdf_paths:
        pages = scan_pages(pdf_to_pages(pdf, work / Path(pdf).stem), ocr)
        for n, doc in enumerate(group_into_invoices(pages), 1):
            result.invoices_seen += 1
            item_id = f"{Path(pdf).stem}-{n:03d}"
            reg = doc.registration_number
            payee_id = by_reg.get(reg, "")
            name = payees[payee_id].display_name if payee_id else (reg or "不明")

            def hold(reason: str, fig=None, detail="", crop=None):
                result.queue.add(ReviewItem(
                    item_id=item_id, payee_id=payee_id, display_name=name,
                    reason=reason, figures=fig or InvoiceFigures(),
                    source_pages=doc.page_numbers,
                    image_path=doc.first_page.image_path,
                    crop=crop, detail=detail))

            if doc.ambiguous:
                hold(AMBIGUOUS_SPLIT, detail=doc.reason)
                continue
            if not payee_id:
                hold(UNKNOWN_PAYEE,
                     detail=f"登録番号 {reg or '（読めず）'} が振込先マスタに"
                            f"ありません")
                continue

            fig, tpl, why = _read_invoice(doc, templates, preset)
            if fig is None:
                hold(why)
                continue

            crop = None
            if tpl and "今回御請求額" in tpl.fields:
                x0, y0, x1, y1 = tpl.fields["今回御請求額"]
                crop = (max(0, x0 - 40), max(0, y0 - 40), x1 + 40, y1 + 40)

            r = reconcile(fig)
            if not r.payable:
                reason = (UNREADABLE if fig.total_billed is None
                          else NO_CORROBORATION if not r.corroborated
                          else RECONCILE_FAILED)
                hold(reason, fig, "; ".join(r.failures), crop)
                continue

            a = history.assess(payee_id, fig.total_billed)
            if a.needs_review:
                hold(OUTLIER, fig, "; ".join(a.reasons), crop)
                continue

            result.resolved.append(Resolved(
                payee_id=payee_id, display_name=name,
                amount=fig.total_billed, registration_number=reg,
                pages=doc.page_numbers, source=Path(pdf).name))

    return result


def to_payments(result: Result, payees: dict[str, Payee]) -> list[Payment]:
    """確定分＋確認済み分を、支払先ごとに合算して振込明細にする。

    確認待ちが残っていれば作らせない（guard_output が例外を出す）。
    """
    result.queue.guard_output()

    totals: dict[str, int] = {}
    for r in result.resolved:
        totals[r.payee_id] = totals.get(r.payee_id, 0) + r.amount
    for it in result.queue.resolved():
        if it.figures.total_billed:
            totals[it.payee_id] = (totals.get(it.payee_id, 0)
                                   + it.figures.total_billed)

    notes_by_payee: dict[str, list[str]] = {}
    for it in result.queue.resolved():
        if it.override:
            notes_by_payee.setdefault(it.payee_id, []).append(
                it.override.describe())

    out: list[Payment] = []
    for pid in sorted(totals):
        p = payees[pid]
        if not p.is_verified:
            raise ValidationError(
                f"{pid} ({p.display_name}): 口座が未確認です。"
                f"確認してから実行してください。")
        out.append(Payment(
            payee_id=pid, bank_code=p.bank_code,
            bank_name_kana=p.bank_name_kana, branch_code=p.branch_code,
            branch_name_kana=p.branch_name_kana, deposit_type=p.deposit_type,
            account_number=p.account_number, payee_name_kana=p.payee_name_kana,
            amount=totals[pid], payee_name_display=p.display_name,
            notes=list(p.conversion_notes) + notes_by_payee.get(pid, []),
            customer_code_1=p.customer_code_1,
            customer_code_2=p.customer_code_2))
    return out
