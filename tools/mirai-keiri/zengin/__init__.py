"""Offline 請求書 -> 全銀 総合振込 pipeline for the clinic's 経理 workflow.

No network calls. No model inference. Every figure that reaches the bank is
traceable to an invoice row and a human-verified master entry.
"""

__all__ = ["kana", "model", "format", "verify", "master", "invoices", "sheet", "xlsx"]
