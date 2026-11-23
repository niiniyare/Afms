"""Back-dated Postings — CTL-04.

Flags shifts submitted more than one day after their shift_date.
Uses modified as the submission timestamp proxy.

T-REG: count flagged.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt, getdate

from forecourt.reports.common import (
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_reg,
	validate_date_range,
)

_BACK_DATE_DAYS = 1


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
			"label": _("Submitted At"),
			"fieldname": "submitted_at",
			"fieldtype": "Datetime",
			"width": 130,
		},
		{
			"label": _("Delay (days)"),
			"fieldname": "delay_days",
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{
			"label": _("Submitted By"),
			"fieldname": "submitted_by",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Flag"),
			"fieldname": "flag",
			"fieldtype": "Data",
			"width": 110,
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
		fields=["name", "station", "shift_date", "modified", "owner"],
		order_by="shift_date asc",
	)

	only_backdated = filters.get("only_backdated")

	result: list[dict] = []
	for s in shifts:
		shift_dt = datetime(*getdate(s.shift_date).timetuple()[:3])
		submitted_at = s.modified
		delay_days = None
		if submitted_at:
			sub_dt = (
				submitted_at
				if isinstance(submitted_at, datetime)
				else datetime.fromisoformat(str(submitted_at))
			)
			delay_days = flt((sub_dt - shift_dt).total_seconds() / 86400, 1)

		late = delay_days is not None and delay_days > _BACK_DATE_DAYS
		flag = _("Back-dated ({0}d)").format(delay_days) if late else ""

		if only_backdated and not flag:
			continue

		result.append(
			{
				"shift_date": s.shift_date,
				"name": s.name,
				"station": s.station,
				"submitted_at": submitted_at,
				"delay_days": delay_days,
				"submitted_by": s.owner or "",
				"flag": flag,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	flagged = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(len(result), _("Shifts"), datatype="Int"),
		summary_card(
			flagged,
			_("Back-dated"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
