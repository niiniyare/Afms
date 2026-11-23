"""Meter Change Register — MTR-04.

One row per submitted Meter Change: when it happened, which nozzle,
old and new meter readings. Used to audit meter replacement history and
verify no shift window was left without a segment.

T-REG totals: row count.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.reports.common import (
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
			"label": _("Changed At"),
			"fieldname": "changed_at",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Meter Change"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Meter Change",
			"width": 160,
		},
		{
			"label": _("Nozzle"),
			"fieldname": "nozzle",
			"fieldtype": "Link",
			"options": "Nozzle",
			"width": 110,
		},
		{"label": _("Reason"), "fieldname": "reason", "fieldtype": "Data", "width": 110},
		{"label": _("Technician"), "fieldname": "technician", "fieldtype": "Data", "width": 130},
		{
			"label": _("Old E-Cash"),
			"fieldname": "old_final_ecash",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{
			"label": _("Old E-Vol"),
			"fieldname": "old_final_evol",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Old M-Vol"),
			"fieldname": "old_final_mvol",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("New E-Cash"),
			"fieldname": "new_start_ecash",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{
			"label": _("New E-Vol"),
			"fieldname": "new_start_evol",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("New M-Vol"),
			"fieldname": "new_start_mvol",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"docstatus": 1}
	if filters.get("company"):
		f["company"] = filters["company"]
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		f["changed_at"] = ["between", [fd + " 00:00:00", td + " 23:59:59"]]
	elif fd:
		f["changed_at"] = [">=", fd + " 00:00:00"]
	elif td:
		f["changed_at"] = ["<=", td + " 23:59:59"]

	if filters.get("nozzle"):
		f["nozzle"] = filters["nozzle"]

	rows = frappe.get_all(
		"Meter Change",
		filters=f,
		fields=[
			"name",
			"station",
			"nozzle",
			"changed_at",
			"reason",
			"technician",
			"old_final_ecash",
			"old_final_evol",
			"old_final_mvol",
			"new_start_ecash",
			"new_start_evol",
			"new_start_mvol",
		],
		order_by="changed_at asc",
	)

	result = [dict(r) for r in rows]

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	summary = [
		summary_card(len(result), _("Meter Changes"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
