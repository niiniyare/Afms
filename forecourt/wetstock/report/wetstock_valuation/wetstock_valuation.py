"""Wetstock Valuation — WET-08.

One row per station + product: book stock, valuation rate, stock value,
variance this month, variance value, own use value, delivery shortage value.

T-ADD; valuation rate is weighted by volume.

NOTE: Stock value comes from ERPNext SLE for tank warehouses. Variance value
and own use value come from Wetstock Ledger Entry fields. This report should
equal the ERPNext Stock Balance for tank warehouses (test requirement T29).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_add,
)


def execute(filters: dict | None = None):
	filters = filters or {}
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Book Stock (L)"),
			"fieldname": "book_stock_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Valuation Rate"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Stock Value"),
			"fieldname": "stock_value",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Variance This Month (L)"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": _("Variance Value"),
			"fieldname": "variance_value",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Own Use Value"),
			"fieldname": "own_use_value",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Delivery Shortage Value"),
			"fieldname": "delivery_shortage_value",
			"fieldtype": "Currency",
			"width": 160,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	as_at = getdate(filters.get("as_at") or today())

	# Month start for variance window
	month_start = as_at.replace(day=1)

	# Permission
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	if filters.get("station"):
		f_perm["station"] = filters["station"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []
	station_filter = f_perm.get("station")

	# --- WLE: shift entries up to as_at for book stock ---
	wle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"entry_type": "Shift",
		"posting_date": ["<=", str(as_at)],
	}
	if filters.get("company"):
		wle_f["company"] = filters["company"]
	if station_filter:
		wle_f["station"] = station_filter
	if filters.get("item"):
		wle_f["item"] = filters["item"]

	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=[
			"tank",
			"station",
			"item",
			"posting_date",
			"dip_l",
			"variance_l",
			"variance_value",
			"valuation_rate",
		],
		order_by="station asc, item asc, posting_date asc",
	)

	# WLE for own use and delivery shortages this month
	wle_month_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"posting_date": ["between", [str(month_start), str(as_at)]],
	}
	if filters.get("company"):
		wle_month_f["company"] = filters["company"]
	if station_filter:
		wle_month_f["station"] = station_filter
	if filters.get("item"):
		wle_month_f["item"] = filters["item"]

	wle_month_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={**wle_month_f, "entry_type": ["in", ["Shift", "Delivery", "Spot Dip", "Transfer"]]},
		fields=[
			"station",
			"item",
			"entry_type",
			"own_use_l",
			"variance_l",
			"variance_value",
			"delivery_variance_l",
			"valuation_rate",
		],
	)

	# Aggregate per station + item
	key_map: dict[tuple, dict] = {}

	for r in wle_rows:
		key = (r.station or "", r.item or "")
		if key not in key_map:
			key_map[key] = {
				"station": r.station,
				"item": r.item,
				"last_dip_l": 0.0,
				"last_valuation_rate": 0.0,
				"month_variance_l": 0.0,
				"month_variance_value": 0.0,
				"own_use_value": 0.0,
				"delivery_shortage_value": 0.0,
			}
		km = key_map[key]
		km["last_dip_l"] = flt(r.dip_l, 2)  # last row wins (sorted by date)
		km["last_valuation_rate"] = flt(r.valuation_rate, 4)

	for r in wle_month_rows:
		key = (r.station or "", r.item or "")
		if key not in key_map:
			key_map[key] = {
				"station": r.station,
				"item": r.item,
				"last_dip_l": 0.0,
				"last_valuation_rate": 0.0,
				"month_variance_l": 0.0,
				"month_variance_value": 0.0,
				"own_use_value": 0.0,
				"delivery_shortage_value": 0.0,
			}
		km = key_map[key]
		if r.entry_type == "Shift":
			km["month_variance_l"] = flt(km["month_variance_l"] + flt(r.variance_l, 2), 2)
			km["month_variance_value"] = flt(km["month_variance_value"] + flt(r.variance_value, 2), 2)
		rate = flt(r.valuation_rate, 4)
		if r.entry_type in ("Transfer",) and r.own_use_l:
			km["own_use_value"] = flt(km["own_use_value"] + flt(r.own_use_l, 2) * rate, 2)
		if r.entry_type == "Delivery" and flt(r.delivery_variance_l) < 0:
			km["delivery_shortage_value"] = flt(
				km["delivery_shortage_value"] + abs(flt(r.delivery_variance_l, 2)) * rate, 2
			)

	result: list[dict] = []
	for km in sorted(key_map.values(), key=lambda x: (x["station"] or "", x["item"] or "")):
		book_l = km["last_dip_l"]
		rate = km["last_valuation_rate"]
		stock_value = flt(book_l * rate, 2)
		result.append(
			{
				"station": km["station"],
				"item": km["item"],
				"book_stock_l": book_l,
				"valuation_rate": rate,
				"stock_value": stock_value,
				"variance_l": km["month_variance_l"],
				"variance_value": km["month_variance_value"],
				"own_use_value": km["own_use_value"],
				"delivery_shortage_value": km["delivery_shortage_value"],
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_stock_value = sum(r["stock_value"] for r in result)
	total_variance_value = sum(r["variance_value"] for r in result)
	summary = [
		summary_card(total_stock_value, _("Total Stock Value"), datatype="Currency"),
		summary_card(total_variance_value, _("Variance Value (Month)"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
