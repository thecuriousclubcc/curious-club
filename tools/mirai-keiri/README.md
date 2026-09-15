# mirai-keiri — 請求書 → 全銀 総合振込ファイル

みらいリハビリ病院 成果物#4（経理）の支払サイドの参照実装。
請求書の明細と振込先マスタから、**振込一覧表（.xlsx）** と
**全銀協規定形式の総合振込ファイル（120バイト固定長 / Shift_JIS）** を生成する。

生成したファイルは人間が FB-Web にアップロードする。**このツールは送信しない。**

## 設計上の約束

| | |
|---|---|
| 外部通信 | しない（`tests/test_offline_guarantee.py` で機械検査） |
| 生成AI | 使わない（同上。別章第6条第1項に対応） |
| 依存パッケージ | なし（Python 3.11 標準ライブラリのみ） |
| 金額の型 | `int`（円）。浮動小数点は使わない |
| 桁あふれ | 切り詰めず**エラーで停止** |
| 変換できない文字 | 推測せず**エラーで停止** |
| 口座情報の出所 | 振込先マスタのみ。請求書からは取らない |

## 使い方

```bash
python3 -m zengin.cli \
  --master   data/payees.csv \
  --invoices data/invoices-2026-10.csv \
  --config   data/requester.json \
  --date     2026-10-31 \
  --history  data/history.json \
  --out      out/
```

出力:
- `out/振込一覧表_20261031.xlsx` — 承認者が確認・押印するシート
- `out/sougou_furikomi_20261031.txt` — FB-Web に送る全銀ファイル

全銀ファイルは、独立した検証器（`zengin/verify.py`）を通過した場合にのみ書き出される。

## 入力

### `requester.json`（委託者 = 病院）
`委託者コード` は銀行から払い出される値。FB-Web の契約書類を見ること。

### `payees.csv`（振込先マスタ）
列: `payee_id, display_name, bank_code, bank_name_kana, branch_code,
branch_name_kana, deposit_type, account_number, payee_name_kana,
fee_borne_by, verified_on, verified_by`

- `payee_name_kana` は**先方の振込先案内・通帳の表記をそのまま**入れる。
  漢字からの自動読み変換はしない（「東」＝ﾋｶﾞｼ/ｱｽﾞﾏ を機械は決められない）。
- `verified_on` / `verified_by` が空の支払先は処理が止まる。
- `deposit_type`: 1=普通 2=当座 4=貯蓄 9=その他
- `fee_borne_by`: `sender`（当方負担）/ `beneficiary`（先方負担→識別表示 `Y`）

### `invoices.csv`（請求書明細）
列: `payee_id, invoice_no, invoice_date, amount, source_file, memo`

1請求書1行。同じ `payee_id` の複数行は自動で合算され、1件の振込になる。
`invoice_no` の重複は二重振込防止のためエラーで止まる。

## 検査基準に引用できるテスト

```bash
python3 -m unittest discover -s tests -v   # 48 tests
```

- `test_zengin.py` — レコード長120バイト、フィールド位置、桁あふれ拒否、
  濁点のバイト数、合計金額の一致、決定性
- `test_offline_guarantee.py` — ネットワーク/AI モジュールの import がないこと（AST検査）、
  ソケットを塞いだ状態で全工程が完走すること

## 本番前に銀行の仕様書と突き合わせる3点

`zengin/format.py` 末尾の FIELD NOTES を参照。鹿児島銀行の
**FB-Webサービス（総合振込）全銀レコードフォーマット**
(`https://www.kagin.co.jp/library/img/fb_manual/19_14_01.pdf`) と照合すること。

1. 手形交換所番号（データ 39-42）— スペース埋め or ゼロ埋め
2. 振込指定区分 / 識別表示（データ 112-113）— 割り当てと必須値
3. 改行コード・EOF（0x1A）・文字コードの扱い

`zengin/format.py` のフィールド表はデータとして宣言してあるので、
PDF と1行ずつ突き合わせられる。
