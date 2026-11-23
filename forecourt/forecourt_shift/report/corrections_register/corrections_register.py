"""Corrections Register — CTL-03.

One row per submitted Shift Correction showing original shift, approver and item count.

T-REG: count corrections.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.reports.common import (
	apply_date_filter,
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
			"label": _("Correction"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Shift Correction",
			"width": 160,
		},
		{
			"label": _("Original Shift"),
			"fieldname": "forecourt_shift",
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
			"label": _("Created At"),
			"fieldname": "creation",
			"fieldtype": "Datetime",
			"width": 130,
		},
		{
			"label": _("Approved By"),
			"fieldname": "approved_by",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Approval State"),
			"fieldname": "approval_state",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Items"),
			"fieldname": "items_count",
			"fieldtype": "Int",
			"width": 70,
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

	cor_f: dict = {"docstatus": 1}
	if filters.get("company"):
		cor_f["company"] = filters["company"]
	if station_filter:
		cor_f["station"] = station_filter
	if filters.get("approval_state"):
		cor_f["approval_state"] = filters["approval_state"]
	apply_date_filter(cor_f, filters)

	cors = frappe.get_all(
		"Shift Correction",
		filters=cor_f,
		fields=["name", "forecourt_shift", "station", "creation", "approved_by", "approval_state"],
		order_by="creation asc",
	)
	if not cors:
		return [], []

	cor_names = [c.name for c in cors]
	item_rows = frappe.get_all(
		"Shift Correction Item",
		filters={"parent": ["in", cor_names]},
		fields=["parent"],
	)
	item_count_map: dict[str, int] = {}
	for it in item_rows:
		item_count_map[it.parent] = item_count_map.get(it.parent, 0) + 1

	result: list[dict] = []
	for c in cors:
		result.append(
			{
				"name": c.name,
				"forecourt_shift": c.forecourt_shift,
				"station": c.station,
				"creation": c.creation,
				"approved_by": c.approved_by or "",
				"approval_state": c.approval_state or "",
				"items_count": item_count_map.get(c.name, 0),
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	summary = [
		summary_card(len(result), _("Corrections"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
