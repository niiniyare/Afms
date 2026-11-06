"""Tank Stock Movement — WET-02.

One row per wetstock ledger entry: opening, receipts, sales, own use,
expected closing stock, dip reading, variance and variance %.
Provides the full stock movement history for each tank.
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
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 110,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Entry Type"),
			"fieldname": "entry_type",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Opening L"),
			"fieldname": "opening_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Receipts L"),
			"fieldname": "receipt_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Sales L"),
			"fieldname": "sales_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Own Use L"),
			"fieldname": "own_use_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 85,
		},
		{
			"label": _("Expected L"),
			"fieldname": "expected_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 95,
		},
		{
			"label": _("Dip L"),
			"fieldname": "dip_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 85,
		},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Variance %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 85,
		},
	]


def _data(filters: dict) -> list[dict]:
	f: dict = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "tank", "item", "entry_type"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	return frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"station",
			"tank",
			"item",
			"posting_date",
			"entry_type",
			"forecourt_shift",
			"opening_l",
			"receipt_l",
			"sales_l",
			"own_use_l",
			"expected_l",
			"dip_l",
			"variance_l",
			"variance_pct",
		],
		order_by="posting_date asc, station asc, tank asc",
	)
