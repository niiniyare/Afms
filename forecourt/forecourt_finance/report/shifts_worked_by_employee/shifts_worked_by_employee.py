"""Shifts Worked by Employee — STF-01.

One row per employee per period: number of shifts worked as cashier,
total fuel litres sold, total cash collected and total shortages.
Reads Cashier Ledger Entry (one row per cashier per shift).

T-ADD: shifts, fuel_l, fuel_amount, difference summed.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_add,
	validate_date_range,
)


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Employee"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Shifts"),
			"fieldname": "shifts",
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"label": _("Fuel Litres"),
			"fieldname": "fuel_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Fuel Amount"),
			"fieldname": "fuel_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Cash"),
			"fieldname": "cash",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Difference"),
			"fieldname": "difference",
			"fieldtype": "Currency",
			"width": 110,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	if filters.get("station"):
		f_perm["station"] = filters["station"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []
	station_filter = f_perm.get("station")

	cle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		cle_f["company"] = filters["company"]
	if station_filter:
		cle_f["station"] = station_filter
	if filters.get("employee"):
		cle_f["cashier"] = filters["employee"]
	apply_date_filter(cle_f, filters)

	cle_rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=cle_f,
		fields=["cashier", "station", "fuel_l", "fuel_amount", "cash", "difference"],
	)

	g: dict[tuple, dict] = {}
	for r in cle_rows:
		key = (r.cashier or "", r.station or "")
		if key not in g:
			g[key] = {
				"cashier": r.cashier,
				"station": r.station,
				"shifts": 0,
				"fuel_l": 0.0,
				"fuel_amount": 0.0,
				"cash": 0.0,
				"difference": 0.0,
			}
		gk = g[key]
		gk["shifts"] += 1
		gk["fuel_l"] = flt(gk["fuel_l"] + flt(r.fuel_l, 2), 2)
		gk["fuel_amount"] = flt(gk["fuel_amount"] + flt(r.fuel_amount, 2), 2)
		gk["cash"] = flt(gk["cash"] + flt(r.cash, 2), 2)
		gk["difference"] = flt(gk["difference"] + flt(r.difference, 2), 2)

	result = sorted(g.values(), key=lambda r: (r["cashier"] or "", r["station"] or ""))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_shifts = sum(r["shifts"] for r in result)
	summary = [
		summary_card(len(result), _("Employees"), datatype="Int"),
		summary_card(total_shifts, _("Total Shifts"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
