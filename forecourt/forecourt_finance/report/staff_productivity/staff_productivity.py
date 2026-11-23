"""Staff Productivity — STF-02.

Per employee: shifts worked, fuel litres per shift, cash per shift,
shortages as % of fuel amount, and shortage count. Ranked by litres
per shift (descending) to identify top performers.

T-WTD: litres_per_shift and cash_per_shift recomputed from totals.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "litres_per_shift",
		"numerator": "fuel_l",
		"denominator": "shifts",
		"multiplier": 1,
		"precision": 2,
	},
	{
		"fieldname": "cash_per_shift",
		"numerator": "fuel_amount",
		"denominator": "shifts",
		"multiplier": 1,
		"precision": 2,
	},
	{
		"fieldname": "shortage_pct",
		"numerator": "total_shortage",
		"denominator": "fuel_amount",
		"multiplier": 100,
		"precision": 2,
	},
]


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
			"label": _("Fuel L"),
			"fieldname": "fuel_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("L / Shift"),
			"fieldname": "litres_per_shift",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Fuel Amount"),
			"fieldname": "fuel_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Cash / Shift"),
			"fieldname": "cash_per_shift",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": _("Shortages"),
			"fieldname": "shortage_count",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Shortage Total"),
			"fieldname": "total_shortage",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Shortage %"),
			"fieldname": "shortage_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 90,
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
		fields=["cashier", "station", "fuel_l", "fuel_amount", "difference"],
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
				"shortage_count": 0,
				"total_shortage": 0.0,
			}
		gk = g[key]
		gk["shifts"] += 1
		gk["fuel_l"] = flt(gk["fuel_l"] + flt(r.fuel_l, 2), 2)
		gk["fuel_amount"] = flt(gk["fuel_amount"] + flt(r.fuel_amount, 2), 2)
		diff = flt(r.difference, 2)
		if diff < 0:
			gk["shortage_count"] += 1
			gk["total_shortage"] = flt(gk["total_shortage"] + abs(diff), 2)

	result_list = []
	for gk in g.values():
		shifts = gk["shifts"]
		fuel_l = flt(gk["fuel_l"], 2)
		fuel_amount = flt(gk["fuel_amount"], 2)
		litres_per_shift = flt((fuel_l / shifts) if shifts else 0, 2)
		cash_per_shift = flt((fuel_amount / shifts) if shifts else 0, 2)
		shortage_pct = flt((gk["total_shortage"] / fuel_amount * 100) if fuel_amount else 0, 2)
		result_list.append(
			{
				"cashier": gk["cashier"],
				"station": gk["station"],
				"shifts": shifts,
				"fuel_l": fuel_l,
				"litres_per_shift": litres_per_shift,
				"fuel_amount": fuel_amount,
				"cash_per_shift": cash_per_shift,
				"shortage_count": gk["shortage_count"],
				"total_shortage": flt(gk["total_shortage"], 2),
				"shortage_pct": shortage_pct,
			}
		)

	result_list.sort(key=lambda r: r["litres_per_shift"], reverse=True)

	cols = _columns()
	total = total_row_wtd(result_list, cols, computed=_COMPUTED) if result_list else {}

	total_shifts = sum(r["shifts"] for r in result_list)
	summary = [
		summary_card(len(result_list), _("Employees"), datatype="Int"),
		summary_card(total_shifts, _("Total Shifts"), datatype="Int"),
	]

	if total:
		result_list.append(total)

	return result_list, summary
