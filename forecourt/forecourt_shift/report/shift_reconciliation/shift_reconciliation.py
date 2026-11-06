"""Shift Reconciliation — SHF-04.

One row per cashier ledger entry: fuel and non-fuel sales, payment types
collected, expected vs accounted cash and the difference.
Gives a manager or auditor a full shift-by-shift accountability picture.
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
		{
			"label": _("Fuel L"),
			"fieldname": "fuel_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Fuel Amt"),
			"fieldname": "fuel_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Non-Fuel Amt"),
			"fieldname": "item_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{"label": _("Expenses"), "fieldname": "expenses", "fieldtype": "Currency", "width": 90},
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
		{
			"label": _("Resolution"),
			"fieldname": "resolution_action",
			"fieldtype": "Data",
			"width": 100,
		},
	]


def _data(filters: dict) -> list[dict]:
	f: dict = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "cashier"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("forecourt_shift"):
		f["forecourt_shift"] = filters["forecourt_shift"]
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
			"fuel_l",
			"fuel_amount",
			"item_amount",
			"cash",
			"mobile",
			"card",
			"credit",
			"expenses",
			"expected",
			"accounted",
			"difference",
			"resolution_action",
		],
		order_by="posting_date asc, station asc, forecourt_shift asc, cashier asc",
	)

	for row in rows:
		row["difference"] = flt(row.get("difference") or 0, 2)

	return rows
