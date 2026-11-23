"""Station Expense Register — EXP-01.

One row per Shift Collection expense line across all submitted shifts,
showing expense type, cashier, amount and the shift it belongs to.

T-ADD: amount summed.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

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
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Date"),
			"fieldname": "shift_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
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
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Reference"),
			"fieldname": "reference",
			"fieldtype": "Data",
			"width": 130,
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

	shift_f: dict = {
		"docstatus": 1,
		"is_cancelled": 0,
	}
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

	coll_f: dict = {
		"parent": ["in", shift_names],
		"collection_type": "Expense",
	}
	if filters.get("expense_type"):
		coll_f["expense_type"] = filters["expense_type"]
	if filters.get("cashier"):
		coll_f["cashier"] = filters["cashier"]

	coll_rows = frappe.get_all(
		"Shift Collection",
		filters=coll_f,
		fields=["parent", "cashier", "expense_type", "amount", "reference"],
		order_by="parent asc",
	)

	result: list[dict] = []
	for c in coll_rows:
		sh = shift_map.get(c.parent)
		if not sh:
			continue
		result.append(
			{
				"shift_date": sh.shift_date,
				"shift": c.parent,
				"station": sh.station,
				"cashier": c.cashier,
				"expense_type": c.expense_type,
				"amount": flt(c.amount, 2),
				"reference": c.reference or "",
			}
		)

	result.sort(key=lambda r: (str(r["shift_date"]), str(r["shift"])))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("Expenses"), datatype="Int"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
