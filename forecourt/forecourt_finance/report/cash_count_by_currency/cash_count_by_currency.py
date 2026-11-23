"""Cash Count by Currency — CSH-07.

One row per currency entry in the Shift Cash Count child table of
each submitted Forecourt Shift in scope. Useful at multi-currency stations
to verify exchange rates and base amounts.

T-ADD totals.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
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
		{"label": _("Date"), "fieldname": "shift_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
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
			"width": 150,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 90,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Exchange Rate"),
			"fieldname": "exchange_rate",
			"fieldtype": "Float",
			"precision": 4,
			"width": 110,
		},
		{
			"label": _("Base Amount"),
			"fieldname": "base_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	shift_f: dict = {"docstatus": 1}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if filters.get("station"):
		shift_f["station"] = filters["station"]
	apply_shift_date_filter(shift_f, filters)
	err = apply_station_permission(shift_f, filters)
	if err:
		return [], []

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "shift_date", "station"],
		order_by="shift_date asc",
	)
	if not shifts:
		return [], []

	shift_map = {s.name: s for s in shifts}
	shift_names = list(shift_map.keys())

	cash_counts = frappe.get_all(
		"Shift Cash Count",
		filters={"parent": ["in", shift_names]},
		fields=["parent", "cashier", "currency", "amount", "exchange_rate", "base_amount"],
		order_by="parent asc",
	)

	requested_cashier = filters.get("cashier")
	requested_currency = filters.get("currency")

	result = []
	for cc in cash_counts:
		if requested_cashier and cc.cashier != requested_cashier:
			continue
		if requested_currency and cc.currency != requested_currency:
			continue
		s = shift_map[cc.parent]
		result.append(
			{
				"shift_date": s.shift_date,
				"forecourt_shift": cc.parent,
				"station": s.station,
				"cashier": cc.cashier,
				"currency": cc.currency,
				"amount": flt(cc.amount, 2),
				"exchange_rate": flt(cc.exchange_rate, 4),
				"base_amount": flt(cc.base_amount, 2),
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_base = sum(r["base_amount"] for r in result)
	summary = [
		summary_card(len(result), _("Count Entries"), datatype="Int"),
		summary_card(total_base, _("Total Base Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
