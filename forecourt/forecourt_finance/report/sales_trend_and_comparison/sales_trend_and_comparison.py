"""Sales Trend and Comparison — SAL-06.

One row per period (week, day or month) in the requested window, with the
same period last year (or prior period) alongside for comparison.

Average per day uses days with closed shifts, not calendar days, so a
station closure does not look like a sales drop.

T-WTD: change % recomputed from summed current and prior.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "change_pct",
		"numerator": "change",
		"denominator": "prior",
		"multiplier": 100,
		"precision": 1,
	}
]


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{"label": _("Period"), "fieldname": "period_label", "fieldtype": "Data", "width": 110},
		{
			"label": _("Measure"),
			"fieldname": "current",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Prior"),
			"fieldname": "prior",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Change"),
			"fieldname": "change",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Change %"),
			"fieldname": "change_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Avg per Day"),
			"fieldname": "avg_per_day",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{"label": _("Days with Data"), "fieldname": "days_with_data", "fieldtype": "Int", "width": 110},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	measure = (filters.get("measure") or "Litres").strip()
	granularity = (filters.get("granularity") or "Week").strip()
	compare_with = (filters.get("compare_with") or "Same period last year").strip()

	to_dt = getdate(filters.get("to_date") or today())
	from_dt = getdate(filters.get("from_date") or (to_dt - timedelta(days=89)))

	# Build comparison offset
	if compare_with == "Same period last year":
		offset_days = 365
	elif compare_with == "Prior period":
		span = (to_dt - from_dt).days + 1
		offset_days = span
	else:
		offset_days = 0

	# Permission filter
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	if filters.get("station"):
		f_perm["station"] = filters["station"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []
	station_filter = f_perm.get("station")

	def _fetch_sle(fd: date, td: date) -> dict[str, float]:
		f: dict = {
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
			"posting_date": ["between", [str(fd), str(td)]],
		}
		if filters.get("company"):
			f["company"] = filters["company"]
		if station_filter:
			f["station"] = station_filter
		if filters.get("item"):
			f["item"] = filters["item"]
		rows = frappe.get_all(
			"Sales Ledger Entry",
			filters=f,
			fields=["posting_date", "qty", "amount"],
		)
		day_map: dict[str, float] = {}
		for r in rows:
			d = str(r.posting_date)
			val = flt(r.qty, 2) if measure == "Litres" else flt(r.amount, 2)
			day_map[d] = flt(day_map.get(d, 0) + val, 2)
		return day_map

	current_map = _fetch_sle(from_dt, to_dt)
	prior_map: dict[str, float] = {}
	if offset_days:
		prior_from = from_dt - timedelta(days=offset_days)
		prior_to = to_dt - timedelta(days=offset_days)
		raw_prior = _fetch_sle(prior_from, prior_to)
		# Re-key prior to current date for alignment
		for d_str, val in raw_prior.items():
			aligned = str(getdate(d_str) + timedelta(days=offset_days))
			prior_map[aligned] = flt(prior_map.get(aligned, 0) + val, 2)

	# Group into periods
	def _period_key(d: date, gran: str) -> str:
		if gran == "Day":
			return str(d)
		if gran == "Week":
			iso = d.isocalendar()
			return f"{iso[0]}-W{iso[1]:02d}"
		# Month
		return f"{d.year}-{d.month:02d}"

	period_current: dict[str, float] = {}
	period_prior: dict[str, float] = {}
	period_days_current: dict[str, int] = {}

	# Collect all days in current range
	day = from_dt
	while day <= to_dt:
		pk = _period_key(day, granularity)
		d_str = str(day)
		if d_str in current_map:
			period_current[pk] = flt(period_current.get(pk, 0) + current_map[d_str], 2)
			period_days_current[pk] = period_days_current.get(pk, 0) + 1
		if d_str in prior_map:
			period_prior[pk] = flt(period_prior.get(pk, 0) + prior_map[d_str], 2)
		day += timedelta(days=1)

	result: list[dict] = []
	for pk in sorted(period_current.keys()):
		current = flt(period_current.get(pk, 0), 2)
		prior = flt(period_prior.get(pk, 0), 2)
		change = flt(current - prior, 2)
		change_pct = flt((change / prior * 100) if prior else 0, 1)
		days_with_data = period_days_current.get(pk, 0)
		avg_per_day = flt(current / days_with_data if days_with_data else 0, 2)
		result.append(
			{
				"period_label": pk,
				"current": current,
				"prior": prior,
				"change": change,
				"change_pct": change_pct,
				"avg_per_day": avg_per_day,
				"days_with_data": days_with_data,
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_current = sum(r["current"] for r in result)
	total_prior = sum(r["prior"] for r in result)
	overall_change_pct = flt(((total_current - total_prior) / total_prior * 100) if total_prior else 0, 1)
	summary = [
		summary_card(total_current, _("Current Period"), datatype="Float"),
		summary_card(total_prior, _("Prior Period"), datatype="Float"),
		summary_card(
			overall_change_pct,
			_("Change %"),
			datatype="Percent",
			indicator="Green" if overall_change_pct >= 0 else "Orange",
		),
	]

	if total:
		result.append(total)

	return result, summary
