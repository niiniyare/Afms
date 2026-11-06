"""Cash Collection — CSH-03.

One row per cashier ledger entry showing the full breakdown of amounts
collected: cash, mobile money, card, credit, vouchers, expenses and
cash drops, plus the expected vs accounted totals and the difference.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150,
		},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Vouchers"),
			"fieldname": "voucher",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Expenses"),
			"fieldname": "expenses",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Drops"),
			"fieldname": "drops",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Float"),
			"fieldname": "float_amount",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Expected"),
			"fieldname": "expected",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Accounted"),
			"fieldname": "accounted",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Difference"),
			"fieldname": "difference",
			"fieldtype": "Currency",
			"width": 100,
		},
	]


def _data(filters: dict) -> list[dict]:
	f: dict = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "cashier"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=f,
		fields=[
			"station",
			"posting_date",
			"forecourt_shift",
			"cashier",
			"cash",
			"mobile",
			"card",
			"credit",
			"voucher",
			"expenses",
			"drops",
			"float_amount",
			"expected",
			"accounted",
			"difference",
		],
		order_by="posting_date asc, station asc, forecourt_shift asc, cashier asc",
	)

	for row in rows:
		row["difference"] = flt(row.get("difference") or 0, 2)

	return rows
