"""Wetstock Variance — FMS-H04.

Per tank per shift: opening, receipts, sales, own use, expected, dip, variance.
Includes cumulative variance % column.
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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{"label": _("Tank"), "fieldname": "tank", "fieldtype": "Link", "options": "Fuel Tank", "width": 100},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 100},
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
			"width": 100,
		},
		{"label": _("Sales L"), "fieldname": "sales_l", "fieldtype": "Float", "precision": 3, "width": 100},
		{
			"label": _("Own Use L"),
			"fieldname": "own_use_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Expected L"),
			"fieldname": "expected_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{"label": _("Dip L"), "fieldname": "dip_l", "fieldtype": "Float", "precision": 3, "width": 90},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 95,
		},
		{
			"label": _("Var %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 3,
			"width": 80,
		},
		{
			"label": _("Cum Var L"),
			"fieldname": "cum_var_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 95,
		},
		{
			"label": _("Cum Var %"),
			"fieldname": "cum_var_pct",
			"fieldtype": "Percent",
			"precision": 3,
			"width": 90,
		},
	]


def _data(filters):
	f = {
		"entry_type": "Shift",
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"posting_date",
			"forecourt_shift",
			"tank",
			"item",
			"opening_l",
			"receipt_l",
			"sales_l",
			"own_use_l",
			"expected_l",
			"dip_l",
			"variance_l",
			"variance_pct",
		],
		order_by="tank asc, posting_date asc, forecourt_shift asc",
	)

	# Compute cumulative variance per tank
	cum: dict[str, list[float]] = {}
	result = []
	for row in rows:
		tank = row.tank or ""
		if tank not in cum:
			cum[tank] = [0.0, 0.0]  # [cum_var_l, cum_sales_l]
		cum[tank][0] = flt(cum[tank][0] + flt(row.variance_l, 3), 3)
		cum[tank][1] = flt(cum[tank][1] + flt(row.sales_l, 3), 3)
		cum_pct = flt(cum[tank][0] / cum[tank][1] * 100, 3) if cum[tank][1] else 0.0
		result.append(
			{
				"posting_date": row.posting_date,
				"forecourt_shift": row.forecourt_shift,
				"tank": row.tank,
				"item": row.item,
				"opening_l": flt(row.opening_l, 3),
				"receipt_l": flt(row.receipt_l, 3),
				"sales_l": flt(row.sales_l, 3),
				"own_use_l": flt(row.own_use_l, 3),
				"expected_l": flt(row.expected_l, 3),
				"dip_l": flt(row.dip_l, 3),
				"variance_l": flt(row.variance_l, 3),
				"variance_pct": flt(row.variance_pct, 3),
				"cum_var_l": cum[tank][0],
				"cum_var_pct": cum_pct,
			}
		)

	return result
