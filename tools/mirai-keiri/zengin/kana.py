"""Half-width katakana normalisation for Zengin (全銀協規定形式) name fields.

Zengin name fields accept only the JIS X 0201 half-width set: half-width
katakana, uppercase A-Z, digits, space and a small symbol set. Voiced marks
(ﾞ/ﾟ) are SEPARATE characters and each consumes one byte of the field.

Every transformation this module applies is reported back to the caller so the
human review sheet can show exactly what was changed. Nothing is silently
dropped: unmappable characters raise, they are never replaced with a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Base katakana -> half-width.
_BASE = {
    "ア": "ｱ", "イ": "ｲ", "ウ": "ｳ", "エ": "ｴ", "オ": "ｵ",
    "カ": "ｶ", "キ": "ｷ", "ク": "ｸ", "ケ": "ｹ", "コ": "ｺ",
    "サ": "ｻ", "シ": "ｼ", "ス": "ｽ", "セ": "ｾ", "ソ": "ｿ",
    "タ": "ﾀ", "チ": "ﾁ", "ツ": "ﾂ", "テ": "ﾃ", "ト": "ﾄ",
    "ナ": "ﾅ", "ニ": "ﾆ", "ヌ": "ﾇ", "ネ": "ﾈ", "ノ": "ﾉ",
    "ハ": "ﾊ", "ヒ": "ﾋ", "フ": "ﾌ", "ヘ": "ﾍ", "ホ": "ﾎ",
    "マ": "ﾏ", "ミ": "ﾐ", "ム": "ﾑ", "メ": "ﾒ", "モ": "ﾓ",
    "ヤ": "ﾔ", "ユ": "ﾕ", "ヨ": "ﾖ",
    "ラ": "ﾗ", "リ": "ﾘ", "ル": "ﾙ", "レ": "ﾚ", "ロ": "ﾛ",
    "ワ": "ﾜ", "ヲ": "ｦ", "ン": "ﾝ",
}

# Voiced / semi-voiced -> base + separate mark.
_DAKUTEN = {
    "ガ": "ｶﾞ", "ギ": "ｷﾞ", "グ": "ｸﾞ", "ゲ": "ｹﾞ", "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ", "ジ": "ｼﾞ", "ズ": "ｽﾞ", "ゼ": "ｾﾞ", "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ", "ヂ": "ﾁﾞ", "ヅ": "ﾂﾞ", "デ": "ﾃﾞ", "ド": "ﾄﾞ",
    "バ": "ﾊﾞ", "ビ": "ﾋﾞ", "ブ": "ﾌﾞ", "ベ": "ﾍﾞ", "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ",
}

# Small kana -> LARGE. Zengin name fields are written in large kana
# (ｷﾔﾉﾝ, not ｷｬﾉﾝ). This is a real transformation, so it is reported.
_SMALL_TO_LARGE = {
    "ァ": "ｱ", "ィ": "ｲ", "ゥ": "ｳ", "ェ": "ｴ", "ォ": "ｵ",
    "ッ": "ﾂ", "ャ": "ﾔ", "ュ": "ﾕ", "ョ": "ﾖ", "ヮ": "ﾜ",
    "ヵ": "ｶ", "ヶ": "ｹ",
}

# Symbols permitted by the Zengin name character set.
_SYMBOLS = {
    "ー": "ｰ",   # U+30FC katakana long vowel
    "-": "-", "ー": "ｰ",
    "（": "(", "）": ")", "(": "(", ")": ")",
    "．": ".", ".": ".",
    "／": "/", "/": "/",
    "￥": "\\", "¥": "\\",
    "，": ",", ",": ",",
    "　": " ", " ": " ",
}

# Hyphen-like codepoints that are NOT the katakana long vowel.
_HYPHENS = {"‐", "‑", "‒", "–", "—", "―",
            "－", "﹣", "−", "・"}

_ALLOWED_SYMBOLS = set(" ().-/\\,")

# Half-width katakana already in the target set: ｦ (FF66) and ｰ..ﾟ (FF70-FF9F).
# FF61-FF65 (｡｢｣､･) are excluded - Zengin name fields do not permit them.
_HALFWIDTH_KANA = {chr(0xFF66)} | {chr(c) for c in range(0xFF70, 0xFFA0)}

# Small half-width kana (FF67-FF6F) must also be folded to large forms.
_HALFWIDTH_SMALL_TO_LARGE = {
    "ｧ": "ｱ", "ｨ": "ｲ", "ｩ": "ｳ", "ｪ": "ｴ", "ｫ": "ｵ",
    "ｬ": "ﾔ", "ｭ": "ﾕ", "ｮ": "ﾖ", "ｯ": "ﾂ",
}


@dataclass
class KanaResult:
    """Outcome of a conversion, including every change made."""

    text: str
    original: str
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.notes)


class KanaError(ValueError):
    """Raised when a character cannot be represented in the Zengin set."""


def _hiragana_to_katakana(ch: str) -> str:
    o = ord(ch)
    if 0x3041 <= o <= 0x3096:
        return chr(o + 0x60)
    return ch


def to_zengin_kana(text: str, *, allow_hiragana: bool = True) -> KanaResult:
    """Convert `text` to the Zengin half-width character set.

    Raises KanaError on any character that has no defined mapping, rather than
    guessing. A wrong payee name costs a 組戻し fee and a delayed payment, so
    an explicit failure is always preferable to a silent substitution.
    """
    out: list[str] = []
    notes: list[str] = []
    saw_small = False
    saw_hiragana = False
    saw_lower = False

    for ch in text:
        if ch in _HYPHENS:
            out.append("-")
            notes.append(f"記号 {ch!r} を '-' に正規化")
            continue

        kata = _hiragana_to_katakana(ch)
        if kata != ch:
            saw_hiragana = True
            if not allow_hiragana:
                raise KanaError(f"ひらがな {ch!r} は許可されていません: {text!r}")
            ch = kata

        if ch in _SMALL_TO_LARGE:
            saw_small = True
            out.append(_SMALL_TO_LARGE[ch])
            continue
        if ch in _HALFWIDTH_SMALL_TO_LARGE:
            saw_small = True
            out.append(_HALFWIDTH_SMALL_TO_LARGE[ch])
            continue
        if ch in _DAKUTEN:
            out.append(_DAKUTEN[ch])
            continue
        if ch in _BASE:
            out.append(_BASE[ch])
            continue
        if ch in _SYMBOLS:
            out.append(_SYMBOLS[ch])
            continue
        if ch in _HALFWIDTH_KANA:
            out.append(ch)
            continue

        # Full-width alphanumerics -> half-width.
        o = ord(ch)
        if 0xFF10 <= o <= 0xFF19:        # ０-９
            out.append(chr(o - 0xFEE0))
            continue
        if 0xFF21 <= o <= 0xFF3A:        # Ａ-Ｚ
            out.append(chr(o - 0xFEE0))
            continue
        if 0xFF41 <= o <= 0xFF5A:        # ａ-ｚ
            saw_lower = True
            out.append(chr(o - 0xFEE0 - 0x20))
            continue
        if ch.isdigit() and ch.isascii():
            out.append(ch)
            continue
        if "A" <= ch <= "Z":
            out.append(ch)
            continue
        if "a" <= ch <= "z":
            saw_lower = True
            out.append(ch.upper())
            continue
        if ch in _ALLOWED_SYMBOLS:
            out.append(ch)
            continue

        raise KanaError(
            f"全銀の文字セットに変換できない文字 {ch!r} (U+{o:04X}) が "
            f"{text!r} に含まれています。振込先マスタを手で修正してください。"
        )

    if saw_hiragana:
        notes.append("ひらがなをカタカナに変換")
    if saw_small:
        notes.append("小書き文字を大文字に変換（全銀の記入規則）")
    if saw_lower:
        notes.append("英小文字を大文字に変換")

    return KanaResult(text="".join(out), original=text, notes=notes)


def byte_length(text: str) -> int:
    """Length in Shift_JIS bytes. Every Zengin-legal character is 1 byte."""
    return len(text.encode("cp932"))
