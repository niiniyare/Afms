"""Run-out Forecast — FMS-H04.

Projects days to run-out per tank using average daily sales
from the last 14 days and current stock (latest dip).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

_FORECAST_DAYS = 14  # rolling average window


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Tank"), "fieldname": "tank", "fieldtype": "Link", "options": "Fuel Tank", "width": 120},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 110},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Current Stock L"),
			"fieldname": "stock_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{
			"label": _("Avg Daily L"),
			"fieldname": "avg_daily_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Days to Run-out"),
			"fieldname": "days_to_runout",
			"fieldtype": "Float",
			"precision": 1,
			"width": 110,
		},
		{"label": _("Est. Run-out Date"), "fieldname": "runout_date", "fieldtype": "Date", "width": 100},
	]


def _data(filters):
	as_of = filters.get("date") or today()
	window_start = add_days(as_of, -_FORECAST_DAYS)

	base_f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("station"):
		base_f["station"] = filters["station"]
	if filters.get("company"):
		base_f["company"] = filters["company"]
	if filters.get("tank"):
		base_f["tank"] = filters["tank"]

	# Current stock: latest dip per tank
	stock_f = {**base_f, "entry_type": "Shift"}
	stock_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=stock_f,
		fields=["tank", "item", "station", "dip_l", "posting_date"],
		order_by="tank asc, posting_date desc, forecourt_shift desc",
	)
	stock_map: dict[str, dict] = {}
	for row in stock_rows:
		if row.tank not in stock_map:
			stock_map[row.tank] = {
				"tank": row.tank,
				"item": row.item,
				"station": row.station,
				"stock_l": flt(row.dip_l, 3),
			}

	# Average daily sales over window
	sales_f = {**base_f, "entry_type": "Shift", "posting_date": ["between", [window_start, as_of]]}
	sales_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=sales_f,
		fields=["tank", "sales_l"],
	)
	sales_total: dict[str, float] = {}
	for row in sales_rows:
		tank = row.tank or ""
		sales_total[tank] = flt(sales_total.get(tank, 0) + flt(row.sales_l, 3), 3)

	result = []
	for tank, info in sorted(stock_map.items(), key=lambda kv: (kv[1]["station"] or "", kv[0])):
		avg_daily = flt(sales_total.get(tank, 0) / _FORECAST_DAYS, 3)
		if avg_daily > 0:
			days = flt(info["stock_l"] / avg_daily, 1)
			runout = add_days(as_of, int(days))
		else:
			days = 0.0
			runout = None
		result.append(
			{
				"tank": info["tank"],
				"item": info["item"],
				"station": info["station"],
				"stock_l": info["stock_l"],
				"avg_daily_l": avg_daily,
				"days_to_runout": days,
				"runout_date": runout,
			}
		)
	return result
