"""業者ごとの「欄の位置」を外部ファイルで持つ。

業者が増えるたびにコードを触るのは現実的でない。請求書のレイアウトは
業者ごとに違い、しかも増えていくので、座標は JSON に出してコードから外す。

■ 解像度の違いを吸収する
スキャンの大きさは毎回同じとは限らない（DPI設定、スキャナの入替、再スキャン）。
座標をそのまま使うと、少しずれた画像で**別の場所を読んでしまう**。
読み間違いではなく「違う欄を読んだ正しい数字」になるので質が悪い。
そこで基準サイズを記録し、実画像の大きさに比例させてから使う。

■ テンプレートの当て方
請求書の登録番号（T+13桁）または payee_id で引く。**推測で当てない。**
引けなければ人に回す。新規業者は稀なので運用できる。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .model import ValidationError
from .tnumber import normalize_tnumber

Box = tuple[int, int, int, int]


@dataclass
class Template:
    template_id: str
    display_name: str
    reference_size: tuple[int, int]        # 座標を測ったときの画像サイズ
    fields: dict[str, Box]
    page: int = 1
    required_fields: list[str] = field(default_factory=list)
    registration_number: str = ""
    payee_id: str = ""
    verified_on: str = ""
    verified_by: str = ""

    def validate(self) -> None:
        w, h = self.reference_size
        if w <= 0 or h <= 0:
            raise ValidationError(
                f"{self.template_id}: reference_size が不正: {self.reference_size}")
        if not self.fields:
            raise ValidationError(f"{self.template_id}: fields が空です")
        for name, box in self.fields.items():
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise ValidationError(
                    f"{self.template_id}: 欄 {name!r} の座標が基準サイズ "
                    f"{w}x{h} の外にあります: {box}")
        for name in self.required_fields:
            if name not in self.fields:
                raise ValidationError(
                    f"{self.template_id}: required_fields の {name!r} が "
                    f"fields にありません")
        if self.page < 1:
            raise ValidationError(f"{self.template_id}: page は1以上")
        if not (self.registration_number or self.payee_id):
            raise ValidationError(
                f"{self.template_id}: registration_number か payee_id の"
                f"どちらかが必要です（引けないテンプレートは使えません）")

    def boxes_for(self, image_size: tuple[int, int]) -> dict[str, Box]:
        """実画像の大きさに合わせて座標を比例させる。"""
        rw, rh = self.reference_size
        iw, ih = image_size
        if (iw, ih) == (rw, rh):
            return dict(self.fields)

        sx, sy = iw / rw, ih / rh
        # 縦横比が大きく違う画像は、別の様式か向きが違う。黙って読まない。
        if abs(sx - sy) / max(sx, sy) > 0.02:
            raise ValidationError(
                f"{self.template_id}: 画像の縦横比が基準と違います"
                f"（基準 {rw}x{rh} / 実際 {iw}x{ih}）。"
                f"向きや様式を確認してください。")
        return {name: (round(x0 * sx), round(y0 * sy),
                       round(x1 * sx), round(y1 * sy))
                for name, (x0, y0, x1, y1) in self.fields.items()}

    @property
    def is_verified(self) -> bool:
        return bool(self.verified_on and self.verified_by)


class TemplateSet:
    def __init__(self, templates: list[Template]):
        self._by_id: dict[str, Template] = {}
        self._by_reg: dict[str, Template] = {}
        self._by_payee: dict[str, Template] = {}
        for t in templates:
            t.validate()
            if t.template_id in self._by_id:
                raise ValidationError(f"template_id が重複: {t.template_id}")
            self._by_id[t.template_id] = t
            if t.registration_number:
                key = normalize_tnumber(t.registration_number)
                if key in self._by_reg:
                    raise ValidationError(
                        f"登録番号 {key} が {self._by_reg[key].template_id} と "
                        f"{t.template_id} で重複しています")
                self._by_reg[key] = t
            if t.payee_id:
                if t.payee_id in self._by_payee:
                    raise ValidationError(
                        f"payee_id {t.payee_id} のテンプレートが重複しています")
                self._by_payee[t.payee_id] = t

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self) -> list[Template]:
        return list(self._by_id.values())

    def find(self, *, registration_number: str = "",
             payee_id: str = "") -> Template | None:
        """完全一致のみ。引けなければ None（＝人へ）。"""
        if registration_number:
            try:
                key = normalize_tnumber(registration_number)
            except ValidationError:
                return None
            if key in self._by_reg:
                return self._by_reg[key]
        if payee_id and payee_id in self._by_payee:
            return self._by_payee[payee_id]
        return None


def load_templates(path: str | Path) -> TemplateSet:
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"テンプレートファイルがありません: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValidationError(f"{p}: JSON として読めません: {e}") from e

    if raw.get("version") != 1:
        raise ValidationError(
            f"{p}: version が 1 ではありません: {raw.get('version')!r}")

    out: list[Template] = []
    for i, item in enumerate(raw.get("templates", [])):
        try:
            out.append(Template(
                template_id=item["template_id"],
                display_name=item.get("display_name", ""),
                reference_size=tuple(item["reference_size"]),
                fields={k: tuple(v) for k, v in item["fields"].items()},
                page=int(item.get("page", 1)),
                required_fields=list(item.get("required_fields", [])),
                registration_number=item.get("registration_number", ""),
                payee_id=item.get("payee_id", ""),
                verified_on=item.get("verified_on", ""),
                verified_by=item.get("verified_by", ""),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise ValidationError(
                f"{p}: templates[{i}] の項目が不正です: {e}") from e
    return TemplateSet(out)
