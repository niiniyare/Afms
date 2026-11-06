"""Payment Reconciliation — PAY-01.

One row per Payment Feed Entry: provider, reference, amount, match status,
linked shift and cashier. Shows unmatched and matched mobile/card payments
so the accountant can track every electronic transaction.
"""

from __future__ import annotations

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Date"),
			"fieldname": "transaction_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Provider"),
			"fieldname": "provider",
			"fieldtype": "Link",
			"options": "Payment Provider",
			"width": 120,
		},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 160},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{"label": _("Payer"), "fieldname": "payer", "fieldtype": "Data", "width": 130},
	]


def _data(filters: dict) -> list[dict]:
	f: dict = {}
	for field in ("station", "provider", "status"):
		if filters.get(field):
			f[field] = filters[field]

	rows = frappe.get_all(
		"Payment Feed Entry",
		filters=f,
		fields=[
			"station",
			"transaction_time",
			"provider",
			"reference",
			"amount",
			"status",
			"cashier",
			"forecourt_shift",
			"payer",
		],
		order_by="transaction_time asc",
	)

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	result = []
	for row in rows:
		txn_date = (row.get("transaction_time") or "")[:10]
		if from_date and txn_date < from_date:
			continue
		if to_date and txn_date > to_date:
			continue
		row["transaction_date"] = txn_date
		result.append(row)

	return result
