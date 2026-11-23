"""Shift Edit Audit Trail — CTL-08.

Queries the Version DocType for all edits made to Forecourt Shift
documents, expanding each version into one row per changed field.

T-REG: count field-change events.
"""

from __future__ import annotations

import json

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
			"label": _("Modified At"),
			"fieldname": "modified",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift_name",
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
			"label": _("Modified By"),
			"fieldname": "modified_by",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Field Changed"),
			"fieldname": "field_changed",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Old Value"),
			"fieldname": "old_value",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("New Value"),
			"fieldname": "new_value",
			"fieldtype": "Data",
			"width": 150,
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

	shift_f: dict = {}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if station_filter:
		shift_f["station"] = station_filter

	if shift_f:
		shift_rows = frappe.get_all(
			"Forecourt Shift",
			filters=shift_f,
			fields=["name", "station"],
		)
		shift_names = [s.name for s in shift_rows]
		station_map = {s.name: s.station for s in shift_rows}
		if not shift_names:
			return [], []
	else:
		shift_names = None
		station_map = {}

	ver_f: dict = {"ref_doctype": "Forecourt Shift"}
	if shift_names is not None:
		ver_f["docname"] = ["in", shift_names]

	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		ver_f["creation"] = ["between", [fd, td + " 23:59:59"]]
	elif fd:
		ver_f["creation"] = [">=", fd]
	elif td:
		ver_f["creation"] = ["<=", td + " 23:59:59"]

	versions = frappe.get_all(
		"Version",
		filters=ver_f,
		fields=["name", "docname", "owner", "creation", "data"],
		order_by="creation desc",
	)

	if not versions and shift_names is None:
		return [], []

	if station_map == {} and versions:
		docnames = list({v.docname for v in versions})
		for s in frappe.get_all(
			"Forecourt Shift",
			filters={"name": ["in", docnames]},
			fields=["name", "station"],
		):
			station_map[s.name] = s.station

	result: list[dict] = []
	for ver in versions:
		try:
			data = json.loads(ver.data or "{}")
		except (json.JSONDecodeError, TypeError):
			continue

		changed = data.get("changed", [])
		if not changed:
			result.append(
				{
					"modified": ver.creation,
					"shift_name": ver.docname,
					"station": station_map.get(ver.docname, ""),
					"modified_by": ver.owner or "",
					"field_changed": "",
					"old_value": "",
					"new_value": "",
				}
			)
		else:
			for change in changed:
				if len(change) >= 3:
					result.append(
						{
							"modified": ver.creation,
							"shift_name": ver.docname,
							"station": station_map.get(ver.docname, ""),
							"modified_by": ver.owner or "",
							"field_changed": str(change[0]),
							"old_value": str(change[1] or ""),
							"new_value": str(change[2] or ""),
						}
					)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="shift_name") if result else {}

	summary = [
		summary_card(len(versions), _("Edit Events"), datatype="Int"),
		summary_card(len(result), _("Field Changes"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
