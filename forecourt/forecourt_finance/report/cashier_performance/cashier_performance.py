"""Cashier Performance — FMS-H05. Rank cashiers by cumulative cash difference."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Rank"), "fieldname": "rank", "fieldtype": "Int", "width": 60},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 160,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Shifts"), "fieldname": "shifts", "fieldtype": "Int", "width": 70},
		{"label": _("Total Diff"), "fieldname": "total_diff", "fieldtype": "Currency", "width": 120},
		{"label": _("Avg Diff"), "fieldname": "avg_diff", "fieldtype": "Currency", "width": 110},
		{"label": _("Short Shifts"), "fieldname": "short_shifts", "fieldtype": "Int", "width": 90},
		{"label": _("Excess Shifts"), "fieldname": "excess_shifts", "fieldtype": "Int", "width": 100},
	]


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=f,
		fields=["cashier", "station", "difference"],
	)

	cashier_map: dict[tuple, dict] = {}
	for row in rows:
		key = (row.cashier or "", row.station or "")
		if key not in cashier_map:
			cashier_map[key] = {
				"cashier": row.cashier,
				"station": row.station,
				"shifts": 0,
				"total_diff": 0.0,
				"short_shifts": 0,
				"excess_shifts": 0,
			}
		d = cashier_map[key]
		diff = flt(row.difference, 2)
		d["shifts"] += 1
		d["total_diff"] = flt(d["total_diff"] + diff, 2)
		if diff < 0:
			d["short_shifts"] += 1
		elif diff > 0:
			d["excess_shifts"] += 1

	result = sorted(cashier_map.values(), key=lambda r: r["total_diff"])
	for idx, row in enumerate(result, 1):
		row["rank"] = idx
		row["avg_diff"] = flt(row["total_diff"] / row["shifts"], 2) if row["shifts"] else 0.0

	return result
