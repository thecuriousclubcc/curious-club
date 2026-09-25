"""読み取り器の実力を数字で出す。

「OCRは信用できない」は正しいが、**どのくらい信用できないか**を知らないと
判断できない。自動で通る率が8割なら、月116件のうち23件が手入力で済む
（今は116件すべて手入力）。3割なら読み取りを入れ替える必要がある。

最も重要な数字は自動通過率ではなく **誤自動通過（false accept）** である。
「自動で通ったが金額が違う」件数。ここは **0でなければならない**。
検算と合意判定はそのために置いてある。0でないなら設計に穴がある。

    python3 -m zengin.measure --invoices 請求書フォルダ \
        --templates data/templates/invoice_templates.json \
        --truth 正解.csv --out 測定結果.csv
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .model import ValidationError
from .reconcile import InvoiceFigures, reconcile
from .readers import cross_read, make_readers
from .templates import TemplateSet, load_templates

# 結果の分類
PASSED = "自動通過"
NEED_READ = "人へ:読めない欄がある"
NEED_RECONCILE = "人へ:検算が合わない"
NEED_CORROBORATION = "人へ:裏取りできない"
NO_TEMPLATE = "人へ:テンプレートが無い"
ERROR = "エラー"


@dataclass
class Outcome:
    source: str
    preset: str
    verdict: str
    amount: int | None = None
    truth: int | None = None
    fields_read: int = 0
    fields_total: int = 0
    detail: str = ""

    @property
    def is_pass(self) -> bool:
        return self.verdict == PASSED

    @property
    def is_false_accept(self) -> bool:
        """自動で通ったのに金額が違う。**あってはならない。**"""
        return (self.is_pass and self.truth is not None
                and self.amount != self.truth)

    @property
    def is_correct_pass(self) -> bool:
        return (self.is_pass and self.truth is not None
                and self.amount == self.truth)


@dataclass
class Report:
    outcomes: list[Outcome] = field(default_factory=list)

    def by_preset(self) -> dict[str, list[Outcome]]:
        out: dict[str, list[Outcome]] = {}
        for o in self.outcomes:
            out.setdefault(o.preset, []).append(o)
        return out

    def summary_lines(self) -> list[str]:
        lines = []
        for preset, os_ in sorted(self.by_preset().items()):
            n = len(os_)
            passed = sum(o.is_pass for o in os_)
            fa = sum(o.is_false_accept for o in os_)
            known = sum(o.truth is not None for o in os_)
            correct = sum(o.is_correct_pass for o in os_)
            rate = f"{passed / n * 100:.0f}%" if n else "—"
            lines.append(f"[{preset}]  {n}件中 自動通過 {passed}件 ({rate})")
            if known:
                lines.append(f"    正解が分かっている {known}件: "
                             f"自動通過して正しい {correct}件 / "
                             f"**誤自動通過 {fa}件**")
                if fa:
                    lines.append("    ⚠ 誤自動通過は0でなければならない。"
                                 "検算か合意判定に穴がある。")
            reasons: dict[str, int] = {}
            for o in os_:
                if not o.is_pass:
                    reasons[o.verdict] = reasons.get(o.verdict, 0) + 1
            for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
                lines.append(f"    {r}: {c}件")
        return lines


def _figures(values: dict[str, int | None], source: str,
             preset: str) -> InvoiceFigures:
    g = values.get
    return InvoiceFigures(
        previous_billed=g("前回御請求額"), payment_received=g("御入金額"),
        carried_over=g("繰越額"), purchases=g("今回御買上額"),
        tax=g("今回消費税額"), subtotal=g("今回合計金額"),
        total_billed=g("今回御請求額"), source_file=source, read_by=preset)


def measure_one(image_path: str | Path, templates: TemplateSet, preset: str,
                *, registration_number: str = "", payee_id: str = "",
                truth: int | None = None) -> Outcome:
    from PIL import Image

    src = Path(image_path).name
    tpl = templates.find(registration_number=registration_number,
                         payee_id=payee_id)
    if tpl is None:
        return Outcome(src, preset, NO_TEMPLATE, truth=truth,
                       detail="登録番号/payee_id からテンプレートを引けなかった")

    try:
        readers = make_readers(preset)
        boxes = tpl.boxes_for(Image.open(image_path).size)
        values = {name: cross_read(str(image_path), box, name, readers).value
                  for name, box in boxes.items()}
    except ValidationError as e:
        return Outcome(src, preset, ERROR, truth=truth, detail=str(e))

    read = sum(v is not None for v in values.values())
    total = len(values)
    fig = _figures(values, src, preset)
    r = reconcile(fig)

    if r.payable:
        return Outcome(src, preset, PASSED, amount=fig.total_billed,
                       truth=truth, fields_read=read, fields_total=total)
    if fig.total_billed is None:
        verdict = NEED_READ
    elif not r.corroborated:
        verdict = NEED_CORROBORATION
    else:
        verdict = NEED_RECONCILE
    return Outcome(src, preset, verdict, amount=fig.total_billed, truth=truth,
                   fields_read=read, fields_total=total,
                   detail="; ".join(r.failures))


def load_truth(path: str | Path) -> dict[str, dict]:
    """正解ファイル: file,registration_number,payee_id,total_billed"""
    out: dict[str, dict] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("file") or "").strip()
            if not name:
                continue
            raw = (row.get("total_billed") or "").strip().replace(",", "")
            out[name] = {
                "registration_number": (row.get("registration_number") or "").strip(),
                "payee_id": (row.get("payee_id") or "").strip(),
                "total_billed": int(raw) if raw.isdigit() else None,
            }
    return out


def write_csv(report: Report, path: str | Path) -> None:
    with Path(path).open("w", encoding="cp932", newline="", errors="replace") as fh:
        w = csv.writer(fh)
        w.writerow(["請求書", "読み取り器", "結果", "読めた金額", "正解",
                    "読めた欄", "欄の総数", "誤自動通過", "詳細"])
        for o in report.outcomes:
            w.writerow([o.source, o.preset, o.verdict,
                        o.amount if o.amount is not None else "",
                        o.truth if o.truth is not None else "",
                        o.fields_read, o.fields_total,
                        "★" if o.is_false_accept else "", o.detail])


def measure_main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="読み取り器の自動通過率を測る")
    ap.add_argument("--invoices", required=True, help="請求書画像のフォルダ")
    ap.add_argument("--templates", required=True)
    ap.add_argument("--truth", help="正解CSV（あれば誤自動通過を検出できる）")
    ap.add_argument("--presets", default="rapidocr,rapidocr+tesseract,tesseract")
    ap.add_argument("--out", help="明細CSVの出力先")
    a = ap.parse_args(argv)

    try:
        templates = load_templates(a.templates)
    except ValidationError as e:
        print(f"エラー: {e}")
        return 1

    truth = load_truth(a.truth) if a.truth else {}
    images = sorted(p for p in Path(a.invoices).iterdir()
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif",
                                            ".tiff"))
    if not images:
        print(f"エラー: {a.invoices} に画像がありません")
        return 1

    report = Report()
    for preset in [p.strip() for p in a.presets.split(",") if p.strip()]:
        for img in images:
            t = truth.get(img.name, {})
            report.outcomes.append(measure_one(
                img, templates, preset,
                registration_number=t.get("registration_number", ""),
                payee_id=t.get("payee_id", ""),
                truth=t.get("total_billed")))

    print(f"請求書 {len(images)}通 を測定しました\n")
    for line in report.summary_lines():
        print(line)

    if a.out:
        write_csv(report, a.out)
        print(f"\n明細: {a.out}")

    fa = sum(o.is_false_accept for o in report.outcomes)
    if fa:
        print(f"\n⚠ 誤自動通過が {fa}件 あります。設計を見直してください。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(measure_main())
