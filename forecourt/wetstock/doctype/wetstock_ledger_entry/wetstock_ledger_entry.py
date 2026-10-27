"""Wetstock Ledger Entry controller (FMS-F15)."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class WetstockLedgerEntry(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_index("Wetstock Ledger Entry", ["station", "posting_date"])
	frappe.db.add_index("Wetstock Ledger Entry", ["company", "posting_date"])
	frappe.db.add_index("Wetstock Ledger Entry", ["tank", "posting_date"])
