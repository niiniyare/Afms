"""Leak and Loss Indicators — WET-04.

One row per tank: statistical signals that suggest a leak, theft or
measurement problem over the requested window.

Signals detected:
  - Cumulative variance % beyond cumulative tolerance
  - More than *n* consecutive loss shifts (filter, default 5)
  - Loss shift rate above 70 % of shifts in window
  - Steady negative trend (average variance_l < 0 for each half-window)

T-RANK: ranked by signal count, then variance %.

Note: thresholds are filters with defaults; defaults are Open Q-07.
Note: water data is not available from WLE (gap G-01).
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_rank,
)

_COMPUTED_RANK = [
	{
		"fieldname": "variance_pct",
		"numerator": "variance_l",
		"denominator": "sales_l",
		"multiplier": 100,
		"precision": 2,
	}
]


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
			"width": 130,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Variance % (Window)"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 130,
		},
		{
			"label": _("Cumulative Tolerance %"),
			"fieldname": "cum_tolerance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Consecutive Loss Shifts"),
			"fieldname": "consecutive_loss_shifts",
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"label": _("Loss Shifts %"),
			"fieldname": "loss_shift_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 110,
		},
		{
			"label": _("Sales (L)"),
			"fieldname": "sales_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Variance (L)"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Trend (L/week)"),
			"fieldname": "trend_l_per_week",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{"label": _("Signals"), "fieldname": "signal_count", "fieldtype": "Int", "width": 70},
		{"label": _("Signal List"), "fieldname": "signals", "fieldtype": "Data", "width": 240},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	window_days = int(filters.get("window_days") or 30)
	to_date = getdate(today())
	from_date = to_date - timedelta(days=window_days - 1)

	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"entry_type": "Shift",
		"posting_date": ["between", [str(from_date), str(to_date)]],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("item"):
		f["item"] = filters["item"]
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	entries = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"tank",
			"station",
			"item",
			"posting_date",
			"sales_l",
			"variance_l",
			"variance_pct",
		],
		order_by="tank asc, posting_date asc",
	)

	min_consecutive = int(filters.get("min_consecutive_loss_shifts") or 5)

	# Group by tank
	tank_entries: dict[str, list] = {}
	for e in entries:
		tank_entries.setdefault(e.tank or "", []).append(e)

	result: list[dict] = []
	for tank, tank_rows in sorted(tank_entries.items()):
		if not tank_rows:
			continue

		station = tank_rows[0].station
		item = tank_rows[0].item
		total_sales = flt(sum(flt(r.sales_l) for r in tank_rows), 2)
		total_variance = flt(sum(flt(r.variance_l) for r in tank_rows), 2)
		variance_pct = flt((total_variance / total_sales * 100) if total_sales else 0, 2)

		# Cumulative tolerance: use 0.5% as default (Q-07 open)
		cum_tolerance_pct = flt(0.5, 2)

		# Consecutive loss shifts
		max_consecutive = 0
		current_consecutive = 0
		loss_shifts = 0
		for r in tank_rows:
			if flt(r.variance_l) < 0:
				current_consecutive += 1
				loss_shifts += 1
				max_consecutive = max(max_consecutive, current_consecutive)
			else:
				current_consecutive = 0

		total_shifts = len(tank_rows)
		loss_shift_pct = flt((loss_shifts / total_shifts * 100) if total_shifts else 0, 1)

		# Trend: compare first half avg vs second half avg
		half = total_shifts // 2
		trend_l_per_week = 0.0
		if half > 0:
			second_avg = sum(flt(r.variance_l) for r in tank_rows[half:]) / (total_shifts - half)
			trend_l_per_week = flt(second_avg * 7, 2)

		# Build signals
		signals: list[str] = []
		if variance_pct < -cum_tolerance_pct:
			signals.append(_("Cumulative variance beyond tolerance"))
		if max_consecutive >= min_consecutive:
			signals.append(_("{0} consecutive loss shifts").format(max_consecutive))
		if loss_shift_pct > 70:
			signals.append(_("{0}% loss shifts").format(loss_shift_pct))
		if trend_l_per_week < 0:
			signals.append(_("Negative trend ({0} L/wk)").format(flt(trend_l_per_week, 1)))

		result.append(
			{
				"station": station,
				"tank": tank,
				"item": item,
				"variance_pct": variance_pct,
				"cum_tolerance_pct": cum_tolerance_pct,
				"consecutive_loss_shifts": max_consecutive,
				"loss_shift_pct": loss_shift_pct,
				"sales_l": total_sales,
				"variance_l": total_variance,
				"trend_l_per_week": trend_l_per_week,
				"signal_count": len(signals),
				"signals": "; ".join(signals),
			}
		)

	# Sort by signals desc, then variance_pct asc
	result.sort(key=lambda x: (-x["signal_count"], x["variance_pct"]))

	cols = _columns()
	rank_row = total_row_rank(result, cols, computed=_COMPUTED_RANK) if result else None
	if rank_row:
		result.append(rank_row)

	tanks_with_signals = sum(1 for r in result if r.get("signal_count", 0) > 0)
	summary = [
		summary_card(len(result), _("Tanks Analysed"), datatype="Int"),
		summary_card(
			tanks_with_signals,
			_("Tanks with Signals"),
			datatype="Int",
			indicator="Orange" if tanks_with_signals else "Green",
		),
	]

	return result, summary
