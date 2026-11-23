"""Custom Number Card methods — FMS-H07."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_first_day, get_last_day, today


@frappe.whitelist()
def cash_short_this_month(**kwargs) -> dict:
	"""Sum of negative cashier differences for the current month."""
	month_start = get_first_day(today())
	month_end = get_last_day(today())
	rows = frappe.get_list(
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

