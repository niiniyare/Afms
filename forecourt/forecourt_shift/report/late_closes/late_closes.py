"""Late Closes (Shift Status and Timeliness) — SHF-06.

One row per submitted shift: when it was expected to close, when it was
actually submitted (proxy for closed_at — G-03 tracks adding a proper
closed_at field), and whether it was late by the threshold.

T-RANK totals: network-average row for hours_to_close; count late.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_rank,
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
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Date"), "fieldname": "shift_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Template"),
			"fieldname": "shift_template",
			"fieldtype": "Link",
			"options": "Shift Template",
			"width": 120,
		},
		{
			"label": _("Expected End"),
			"fieldname": "shift_end",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{
			"label": _("Closed At"),
			"fieldname": "closed_at",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Hours to Close"),
			"fieldname": "hours_to_close",
			"fieldtype": "Float",
			"precision": 1,
			"width": 110,
		},
		{"label": _("Late"), "fieldname": "is_late", "fieldtype": "Check", "width": 60},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	shift_f = {"docstatus": 1}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	apply_shift_date_filter(shift_f, filters)
	err = apply_station_permission(shift_f, filters)
	if err:
		return [], []

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_template", "shift_date", "shift_end", "modified", "status"],
		order_by="shift_date asc, station asc",
	)

	late_threshold = flt(filters.get("late_hours") or 12)
	late_only = filters.get("late_only")

	rows = []
	total_hours = 0.0
	late_count = 0
	hours_count = 0

	for s in shifts:
		closed_at = s.modified  # G-03 workaround: use modified as proxy
		hours_to_close = None
		is_late = 0

		if s.shift_end and closed_at:
			end_dt = (
				s.shift_end if isinstance(s.shift_end, datetime) else datetime.fromisoformat(str(s.shift_end))
			)
			closed_dt = (
				closed_at if isinstance(closed_at, datetime) else datetime.fromisoformat(str(closed_at))
			)
			diff_hours = (closed_dt - end_dt).total_seconds() / 3600
			hours_to_close = flt(diff_hours, 1)
			if hours_to_close > late_threshold:
				is_late = 1

		if late_only and not is_late:
			continue

		if hours_to_close is not None:
			total_hours += hours_to_close
			hours_count += 1
		if is_late:
			late_count += 1

		rows.append(
			{
				"station": s.station,
				"shift_date": s.shift_date,
				"name": s.name,
				"shift_template": s.shift_template,
				"shift_end": s.shift_end,
				"status": s.status,
				"closed_at": closed_at,
				"hours_to_close": hours_to_close,
				"is_late": is_late,
			}
		)

	avg_hours = flt(total_hours / hours_count, 1) if hours_count else 0.0

	cols = _columns()
	rank_row = total_row_rank(rows, cols) if rows else None
	if rank_row:
		rows.append(rank_row)

	summary = [
		summary_card(len(shifts), _("Shifts Expected"), datatype="Int"),
		summary_card(len(rows), _("Closed"), datatype="Int"),
		summary_card(late_count, _("Late"), datatype="Int", indicator="Orange" if late_count else "Green"),
		summary_card(avg_hours, _("Avg Hours to Close"), datatype="Float"),
	]

	return rows, summary
