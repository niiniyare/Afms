"""Cashier Ledger Entry controller (FMS-F15)."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class CashierLedgerEntry(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_index("Cashier Ledger Entry", ["station", "posting_date"])
	frappe.db.add_index("Cashier Ledger Entry", ["company", "posting_date"])
	frappe.db.add_index("Cashier Ledger Entry", ["cashier", "posting_date"])
