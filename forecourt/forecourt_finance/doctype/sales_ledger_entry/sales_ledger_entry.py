"""Sales Ledger Entry controller (FMS-F15)."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class SalesLedgerEntry(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_index("Sales Ledger Entry", ["station", "posting_date"])
	frappe.db.add_index("Sales Ledger Entry", ["company", "posting_date"])
	frappe.db.add_index("Sales Ledger Entry", ["item", "posting_date"])
	frappe.db.add_index("Sales Ledger Entry", ["cashier", "posting_date"])
