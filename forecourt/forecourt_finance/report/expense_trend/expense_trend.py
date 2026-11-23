"""Expense Trend — EXP-02.

Expense amounts grouped by period (Month/Week) and expense type.
One row per period/expense_type/station combination.

T-WTD: (no computed ratios — simple T-ADD would suffice, but T-WTD used for
        period header rows in the total).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from forecourt.reports.common import (
	apply_date_filter,
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_add,
	validate_date_range,
)


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"), max_days=548)
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Period"),
			"fieldname": "period_label",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Expense Type"),
			"fieldname": "expense_type",
			"fieldtype": "Link",
			"options": "Expense Type",
			"width": 140,
		},
		{
			"label": _("Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 120,
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

	shift_f: dict = {"docstatus": 1, "is_cancelled": 0}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if station_filter:
		shift_f["station"] = station_filter
	apply_shift_date_filter(shift_f, filters)

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_date"],
	)
	if not shifts:
		return [], []

	shift_names = [s.name for s in shifts]
	shift_map = {s.name: s for s in shifts}

	granularity = (filters.get("granularity") or "Month").strip()

	def _period_key(d) -> str:
		dt = getdate(d)
		if granularity == "Week":
			iso = dt.isocalendar()
			return f"{iso[0]}-W{iso[1]:02d}"
		return f"{dt.year}-{dt.month:02d}"

	coll_f: dict = {"parent": ["in", shift_names], "collection_type": "Expense"}
	if filters.get("expense_type"):
		coll_f["expense_type"] = filters["expense_type"]

	coll_rows = frappe.get_all(
		"Shift Collection",
		filters=coll_f,
		fields=["parent", "expense_type", "amount"],
	)

	g: dict[tuple, dict] = {}
	for c in coll_rows:
		sh = shift_map.get(c.parent)
		if not sh:
			continue
		period = _period_key(sh.shift_date)
		key = (period, sh.station or "", c.expense_type or "")
		if key not in g:
			g[key] = {
				"period_label": period,
				"station": sh.station,
				"expense_type": c.expense_type,
				"count": 0,
				"amount": 0.0,
			}
		g[key]["count"] += 1
		g[key]["amount"] = flt(g[key]["amount"] + flt(c.amount, 2), 2)

	result = [gk for _, gk in sorted(g.items())]

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(total_amount, _("Total Expenses"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
