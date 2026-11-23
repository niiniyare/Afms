"""Variance Reason Analysis — CTL-05.

Groups Shift Resolution children from submitted shifts by reason.
Fetches applies_to from Variance Reason master.

T-WTD: frequency_pct = count / _total_count * 100.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "frequency_pct",
		"numerator": "count",
		"denominator": "_total_count",
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
		{
			"label": _("Reason"),
			"fieldname": "reason",
			"fieldtype": "Link",
			"options": "Variance Reason",
			"width": 160,
		},
		{
			"label": _("Applies To"),
			"fieldname": "applies_to",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Total Amount"),
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Total Volume (L)"),
			"fieldname": "total_volume_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 130,
		},
		{
			"label": _("Frequency %"),
			"fieldname": "frequency_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 110,
		},
		{
			"label": _("_Total Count"),
			"fieldname": "_total_count",
			"fieldtype": "Int",
			"hidden": 1,
			"width": 0,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	if filters.get("station"):
		f_perm["station"] = filters["station"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []
	station_filter = f_perm.get("station")

	shift_f: dict = {"docstatus": 1}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if station_filter:
		shift_f["station"] = station_filter
	apply_shift_date_filter(shift_f, filters)

	shift_names = frappe.get_all("Forecourt Shift", filters=shift_f, pluck="name")
	if not shift_names:
		return [], []

	res_f: dict = {"parent": ["in", shift_names], "parenttype": "Forecourt Shift"}
	if filters.get("resolution_for"):
		res_f["resolution_for"] = filters["resolution_for"]

	resolutions = frappe.get_all(
		"Shift Resolution",
		filters=res_f,
		fields=["reason", "amount", "volume_l"],
	)

	if not resolutions:
		return [], []

	reason_names = list({r.reason for r in resolutions if r.reason})
	reason_map: dict[str, str] = {}
	if reason_names:
		for vr in frappe.get_all(
			"Variance Reason",
			filters={"name": ["in", reason_names]},
			fields=["name", "applies_to"],
		):
			reason_map[vr.name] = vr.applies_to or ""

	groups: dict[str, dict] = {}
	for r in resolutions:
		key = r.reason or ""
		if key not in groups:
			groups[key] = {"count": 0, "total_amount": 0.0, "total_volume_l": 0.0}
		groups[key]["count"] += 1
		groups[key]["total_amount"] += flt(r.amount)
		groups[key]["total_volume_l"] += flt(r.volume_l)

	total_count = sum(g["count"] for g in groups.values())

	result: list[dict] = []
	for reason, g in sorted(groups.items(), key=lambda x: -x[1]["count"]):
		freq = flt(g["count"] / total_count * 100, 1) if total_count else 0.0
		result.append(
			{
				"reason": reason,
				"applies_to": reason_map.get(reason, ""),
				"count": g["count"],
				"total_amount": flt(g["total_amount"], 2),
				"total_volume_l": flt(g["total_volume_l"], 3),
				"frequency_pct": freq,
				"_total_count": total_count,
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_amount = flt(sum(r["total_amount"] for r in result), 2)
	summary = [
		summary_card(total_count, _("Resolutions"), datatype="Int"),
		summary_card(len(result), _("Distinct Reasons"), datatype="Int"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
