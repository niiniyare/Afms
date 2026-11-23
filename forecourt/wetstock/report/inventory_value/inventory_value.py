"""Inventory Value — WET-08.

One row per active tank: current stock in litres (from the most recent
Wetstock Ledger Entry Shift row up to as_at) and its value at the last
posted valuation rate. Used for balance-sheet and insurance valuations.

T-ADD totals on stock_l and value.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today

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
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 150,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("As At"),
			"fieldname": "as_at",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Last Shift"),
			"fieldname": "last_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Stock L"),
			"fieldname": "stock_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Valuation Rate"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Value"),
			"fieldname": "value",
			"fieldtype": "Currency",
			"width": 130,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"disabled": 0}
	if filters.get("company"):
		f["company"] = filters["company"]
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	tanks = frappe.get_all(
		"Fuel Tank",
		filters=f,
		fields=["name", "station", "item"],
		order_by="station asc, name asc",
	)
	if not tanks:
		return [], []

	tank_names = [t.name for t in tanks]
	as_at = filters.get("as_at") or today()

	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={
			"tank": ["in", tank_names],
			"entry_type": "Shift",
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
			"posting_date": ["<=", as_at],
		},
		fields=["tank", "posting_date", "forecourt_shift", "dip_l", "valuation_rate"],
		order_by="posting_date desc, creation desc",
	)

	# Latest WLE per tank
	latest: dict[str, dict] = {}
	for r in wle_rows:
		if r.tank not in latest:
			latest[r.tank] = dict(r)

	result = []
	for t in tanks:
		wle = latest.get(t.name)
		stock_l = flt(wle["dip_l"], 3) if wle else 0.0
		rate = flt(wle["valuation_rate"], 4) if wle else 0.0
		value = flt(stock_l * rate, 2)
		result.append(
			{
				"station": t.station,
				"tank": t.name,
				"item": t.item,
				"as_at": as_at,
				"last_shift": wle["forecourt_shift"] if wle else "",
				"stock_l": stock_l,
				"valuation_rate": rate,
				"value": value,
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_value = sum(r["value"] for r in result)

	summary = [
		summary_card(len(result), _("Tanks"), datatype="Int"),
		summary_card(total_value, _("Total Value"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
