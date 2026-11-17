"""Monthly Station Report — SHF-07.

One row per calendar day: litres sold, sales by payment type, deliveries,
tank variance and cashier difference. The monthly companion of the DSR.

T-WTD totals with weighted variance %.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate

from forecourt.reports.common import (
	apply_date_filter,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "variance_pct",
		"numerator": "variance_l",
		"denominator": "total_litres",
		"multiplier": 100,
		"precision": 2,
	}
]


def execute(filters: dict | None = None):
	filters = filters or {}
	if not filters.get("station"):
		frappe.throw(_("Station is required for Monthly Station Report"))
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{"label": _("Day"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Total L"),
			"fieldname": "total_litres",
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{"label": _("Sales"), "fieldname": "sales", "fieldtype": "Currency", "width": 110},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Deliveries L"),
			"fieldname": "deliveries_l",
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 80},
		{"label": _("Cashier Diff"), "fieldname": "cashier_diff", "fieldtype": "Currency", "width": 100},
		{"label": _("Expenses"), "fieldname": "expenses", "fieldtype": "Currency", "width": 100},
	]


def _empty_day(d: date) -> dict:
	return {
		"posting_date": d,
		"total_litres": 0.0,
		"sales": 0.0,
		"cash": 0.0,
		"mobile": 0.0,
		"card": 0.0,
		"credit": 0.0,
		"deliveries_l": 0.0,
		"variance_l": 0.0,
		"variance_pct": 0.0,
		"cashier_diff": 0.0,
		"expenses": 0.0,
	}


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	station = filters["station"]
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	# Build day map covering every calendar day in the range
	day_map: dict[date, dict] = {}
	if from_date and to_date:
		cursor = getdate(from_date)
		end = getdate(to_date)
		while cursor <= end:
			day_map[cursor] = _empty_day(cursor)
			cursor += timedelta(days=1)

	base = {"is_cancelled": 0, "superseded_by": ["is", "not set"], "station": station}

	# Sales Ledger Entry: fuel only, aggregate by day and payment_type
	sle_f = {**base, "is_fuel": 1}
	apply_date_filter(sle_f, filters)
	sle_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=sle_f,
		fields=["posting_date", "qty", "amount", "payment_type"],
	)
	for r in sle_rows:
		d = getdate(r.posting_date)
		if d not in day_map:
			day_map[d] = _empty_day(d)
		dm = day_map[d]
		dm["total_litres"] = flt(dm["total_litres"] + flt(r.qty, 3), 3)
		dm["sales"] = flt(dm["sales"] + flt(r.amount, 2), 2)
		pt = (r.payment_type or "").lower()
		if "cash" in pt:
			dm["cash"] = flt(dm["cash"] + flt(r.amount, 2), 2)
		elif "mobile" in pt:
			dm["mobile"] = flt(dm["mobile"] + flt(r.amount, 2), 2)
		elif "card" in pt:
			dm["card"] = flt(dm["card"] + flt(r.amount, 2), 2)
		elif "credit" in pt:
			dm["credit"] = flt(dm["credit"] + flt(r.amount, 2), 2)

	# Wetstock Ledger Entry: Shift type, deliveries + variance per day
	wle_f = {**base, "entry_type": "Shift"}
	apply_date_filter(wle_f, filters)
	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=["posting_date", "receipt_l", "variance_l"],
	)
	for r in wle_rows:
		d = getdate(r.posting_date)
		if d not in day_map:
			day_map[d] = _empty_day(d)
		dm = day_map[d]
		dm["deliveries_l"] = flt(dm["deliveries_l"] + flt(r.receipt_l, 3), 3)
		dm["variance_l"] = flt(dm["variance_l"] + flt(r.variance_l, 3), 3)

	# Cashier Ledger Entry: difference and expenses per day
	cle_f = {**base}
	apply_date_filter(cle_f, filters)
	cle_rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=cle_f,
		fields=["posting_date", "difference", "expenses"],
	)
	for r in cle_rows:
		d = getdate(r.posting_date)
		if d not in day_map:
			day_map[d] = _empty_day(d)
		dm = day_map[d]
		dm["cashier_diff"] = flt(dm["cashier_diff"] + flt(r.difference, 2), 2)
		dm["expenses"] = flt(dm["expenses"] + flt(r.expenses, 2), 2)

	# Recompute variance_pct per day
	for dm in day_map.values():
		if dm["total_litres"]:
			dm["variance_pct"] = flt(dm["variance_l"] / dm["total_litres"] * 100, 2)

	rows = sorted(day_map.values(), key=lambda r: r["posting_date"])

	cols = _columns()
	total = total_row_wtd(rows, cols, computed=_COMPUTED) if rows else {}

	total_litres = total.get("total_litres", 0.0)
	total_sales = total.get("sales", 0.0)
	total_variance_pct = total.get("variance_pct", 0.0)
	total_cashier_diff = total.get("cashier_diff", 0.0)

	summary = [
		summary_card(total_litres, _("Total Litres"), datatype="Float"),
		summary_card(total_sales, _("Sales"), datatype="Currency"),
		summary_card(
			total_variance_pct,
			_("Variance %"),
			datatype="Percent",
			indicator="Orange" if abs(total_variance_pct) > 1 else "Green",
		),
		summary_card(
			total_cashier_diff,
			_("Cashier Difference"),
			datatype="Currency",
			indicator="Orange" if total_cashier_diff else "Green",
		),
	]

	if total:
		rows.append(total)

	return rows, summary
