"""Payment Reconciliation — PAY-01.

One row per Payment Feed Entry: provider, reference, amount, match status,
linked shift and cashier. Shows unmatched and matched mobile/card payments
so the accountant can track every electronic transaction.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.reports.common import apply_station_permission, validate_date_range


def execute(filters=None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
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
	for field in ("provider", "status"):
		if filters.get(field):
			f[field] = filters[field]

	# Date filter on transaction_time (Datetime); apply at query level to avoid
	# fetching unbounded result sets.  transaction_time stores full ISO datetime
	# but date string comparison works because ISO format sorts lexicographically.
	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		f["transaction_time"] = ["between", [fd + " 00:00:00", td + " 23:59:59"]]
	elif fd:
		f["transaction_time"] = [">=", fd + " 00:00:00"]
	elif td:
		f["transaction_time"] = ["<=", td + " 23:59:59"]

	err = apply_station_permission(f, filters)
	if err:
		return []

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

	result = []
	for row in rows:
		row["transaction_date"] = (row.get("transaction_time") or "")[:10]
		result.append(row)

	return result
