"""Custom Number Card methods — FMS-H07."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_first_day, get_last_day, today


@frappe.whitelist()
def cash_short_this_month(**kwargs) -> dict:
	"""Sum of negative cashier differences for the current month."""
	month_start = get_first_day(today())
	month_end = get_last_day(today())
	rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters={
			"posting_date": ["between", [month_start, month_end]],
			"difference": ["<", 0],
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
		},
		fields=["difference"],
	)
	total = flt(sum(flt(r.difference, 2) for r in rows), 2)
	return {"value": abs(total), "fieldtype": "Currency"}


@frappe.whitelist()
def tanks_below_reorder(**kwargs) -> dict:
	"""Count tanks projected to run out within 2 days based on 14-day rolling sales."""
	from forecourt.wetstock.report.run_out_forecast.run_out_forecast import _data as forecast_data

	rows = forecast_data({})
	count = sum(1 for r in rows if 0 < flt(r.get("days_to_runout", 99)) <= 2)
	return {"value": count, "fieldtype": "Int"}


@frappe.whitelist()
def cumulative_tank_variance_chart(**kwargs) -> dict:
	"""Cumulative variance % per tank over time for a line chart."""
	from frappe.utils import add_days

	days = 30
	end = today()
	start = add_days(end, -days)

	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={
			"entry_type": "Shift",
			"posting_date": ["between", [start, end]],
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
		},
		fields=["posting_date", "tank", "variance_l", "sales_l"],
		order_by="tank asc, posting_date asc",
	)

	# Build cumulative variance % per tank per day
	tank_cum: dict[str, list[float, float]] = {}
	dataset: dict[str, list] = {}
	seen_dates: list[str] = []

	for row in rows:
		tank = row.tank or ""
		date_str = str(row.posting_date)
		if tank not in tank_cum:
			tank_cum[tank] = [0.0, 0.0]
		if date_str not in seen_dates:
			seen_dates.append(date_str)

	for row in rows:
		tank = row.tank or ""
		date_str = str(row.posting_date)
		tank_cum[tank][0] = flt(tank_cum[tank][0] + flt(row.variance_l, 3), 3)
		tank_cum[tank][1] = flt(tank_cum[tank][1] + flt(row.sales_l, 3), 3)
		pct = flt(tank_cum[tank][0] / tank_cum[tank][1] * 100, 2) if tank_cum[tank][1] else 0.0
		if tank not in dataset:
			dataset[tank] = []
		dataset[tank].append(pct)

	return {
		"labels": seen_dates,
		"datasets": [{"name": tank, "values": vals} for tank, vals in dataset.items()],
	}
