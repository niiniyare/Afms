"""Run-out Forecast — FMS-H04.

Projects days to run-out per tank using average daily sales
from the last 14 days and current stock (latest dip).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from forecourt.reports.common import apply_station_permission

_FORECAST_DAYS = 14  # rolling average window

# Status values for the status column
_STATUS_FORECAST = "Forecast"
_STATUS_NO_SALES = "No recent sales"
_STATUS_NO_STOCK = "No stock"


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
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]


def _forecast_row(stock_l: float, avg_daily: float, as_of: str) -> dict:
	"""
	Pure calculation: given current stock and average daily sales, return
	the forecast fields (days_to_runout, runout_date, status).

	Extracted for unit testing without DB access.
	"""
	if stock_l <= 0:
		return {"days_to_runout": 0.0, "runout_date": as_of, "status": _STATUS_NO_STOCK}
	if avg_daily <= 0:
		# Tank has stock but no recorded sales in the lookback window —
		# cannot produce a forecast without consumption data.
		return {"days_to_runout": None, "runout_date": None, "status": _STATUS_NO_SALES}
	days = flt(stock_l / avg_daily, 1)
	runout = add_days(as_of, int(days))
	return {"days_to_runout": days, "runout_date": runout, "status": _STATUS_FORECAST}


def _data(filters):
	as_of = filters.get("date") or today()
	window_start = add_days(as_of, -_FORECAST_DAYS)

	base_f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("company"):
		base_f["company"] = filters["company"]
	if filters.get("tank"):
		base_f["tank"] = filters["tank"]
	err = apply_station_permission(base_f, filters)
	if err:
		return []

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
		fc = _forecast_row(info["stock_l"], avg_daily, as_of)
		result.append(
			{
				"tank": info["tank"],
				"item": info["item"],
				"station": info["station"],
				"stock_l": info["stock_l"],
				"avg_daily_l": avg_daily,
				"days_to_runout": fc["days_to_runout"],
				"runout_date": fc["runout_date"],
				"status": fc["status"],
			}
		)
	return result
