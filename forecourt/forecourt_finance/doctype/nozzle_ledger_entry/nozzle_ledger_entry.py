"""Nozzle Ledger Entry controller (FMS-F15)."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class NozzleLedgerEntry(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_index("Nozzle Ledger Entry", ["station", "posting_date"])
	frappe.db.add_index("Nozzle Ledger Entry", ["company", "posting_date"])
	frappe.db.add_index("Nozzle Ledger Entry", ["nozzle", "posting_date"])
