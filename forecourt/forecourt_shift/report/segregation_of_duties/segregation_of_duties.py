"""Segregation of Duties — CTL-07.

Flags submitted shifts where the approver is the same person
who submitted (owner == approved_by).

T-REG: count flagged violations.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.reports.common import (
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_reg,
	validate_date_range,
)


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
			"label": _("Shift Date"),
			"fieldname": "shift_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Shift"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Submitted By"),
			"fieldname": "submitted_by",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Approved By"),
			"fieldname": "approved_by",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Flag"),
			"fieldname": "flag",
			"fieldtype": "Data",
			"width": 120,
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

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "shift_date", "station", "owner", "approved_by"],
		order_by="shift_date asc",
	)

	only_violations = filters.get("only_violations")

	result: list[dict] = []
	for s in shifts:
		flag = ""
		if s.approved_by and s.owner and s.approved_by == s.owner:
			flag = _("Self-approved")

		if only_violations and not flag:
			continue

		result.append(
			{
				"shift_date": s.shift_date,
				"name": s.name,
				"station": s.station,
				"submitted_by": s.owner or "",
				"approved_by": s.approved_by or "",
				"flag": flag,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	violations = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(len(result), _("Shifts"), datatype="Int"),
		summary_card(
			violations,
			_("Violations"),
			datatype="Int",
			indicator="Red" if violations else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
