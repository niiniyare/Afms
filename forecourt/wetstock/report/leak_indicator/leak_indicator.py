"""Leak Indicator — WET-04.

Per-tank summary of wetstock variance over the period. Consistent or
large negative variance (actual dip < expected) is a leak signal.
Source: Wetstock Ledger Entry, entry_type Shift.

No T-* total row; summary shows tanks flagged.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	validate_date_range,
)

_FLAG_THRESHOLD_L = -20.0  # cumulative variance below this triggers flag


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
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
			"width": 120,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{"label": _("Shifts"), "fieldname": "shift_count", "fieldtype": "Int", "width": 70},
		{
			"label": _("Total Variance L"),
			"fieldname": "total_variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 120,
		},
		{
			"label": _("Avg per Shift L"),
			"fieldname": "avg_variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 120,
		},
		{
			"label": _("Worst Shift L"),
			"fieldname": "worst_variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{
			"label": _("Negative Shifts"),
			"fieldname": "negative_count",
			"fieldtype": "Int",
			"width": 100,
		},
		{"label": _("Flag"), "fieldname": "flag", "fieldtype": "Data", "width": 80},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"entry_type": "Shift",
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=["station", "tank", "item", "variance_l"],
		order_by="station asc, tank asc",
	)

	tank_map: dict[tuple, dict] = {}
	for r in rows:
		key = (r.station or "", r.tank or "", r.item or "")
		if key not in tank_map:
			tank_map[key] = {
				"station": r.station,
				"tank": r.tank,
				"item": r.item,
				"shift_count": 0,
				"total_variance_l": 0.0,
				"worst_variance_l": 0.0,
				"negative_count": 0,
			}
		tm = tank_map[key]
		v = flt(r.variance_l, 3)
		tm["shift_count"] += 1
		tm["total_variance_l"] = flt(tm["total_variance_l"] + v, 3)
		if v < tm["worst_variance_l"]:
			tm["worst_variance_l"] = v
		if v < 0:
			tm["negative_count"] += 1

	threshold = flt(filters.get("threshold_l") or _FLAG_THRESHOLD_L, 3)
	flagged = 0

	result = []
	for tm in sorted(tank_map.values(), key=lambda x: (x["station"], x["tank"])):
		avg = flt(tm["total_variance_l"] / tm["shift_count"], 3) if tm["shift_count"] else 0.0
		is_flagged = tm["total_variance_l"] < threshold
		tm["avg_variance_l"] = avg
		tm["flag"] = _("Flagged") if is_flagged else ""
		if is_flagged:
			flagged += 1
		result.append(tm)

	summary = [
		summary_card(len(result), _("Tanks Analysed"), datatype="Int"),
		summary_card(
			flagged,
			_("Flagged"),
			datatype="Int",
			indicator="Red" if flagged else "Green",
		),
	]

	return result, summary
