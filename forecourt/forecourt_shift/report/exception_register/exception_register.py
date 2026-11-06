"""Exception Register — FMS-H06.

Lists shifts that have write-offs, variances above tolerance, corrections,
or approval events, for audit and management review.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Date"), "fieldname": "shift_date", "fieldtype": "Date", "width": 90},
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
		{"label": _("Exception Type"), "fieldname": "exception_type", "fieldtype": "Data", "width": 140},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Amount / L"), "fieldname": "value", "fieldtype": "Float", "precision": 2, "width": 100},
		{
			"label": _("Approved By"),
			"fieldname": "approved_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 120,
		},
		{
			"label": _("Correction"),
			"fieldname": "correction",
			"fieldtype": "Link",
			"options": "Shift Correction",
			"width": 140,
		},
	]


def _data(filters):
	shift_f = {"docstatus": 1}
	if filters.get("station"):
		shift_f["station"] = filters["station"]
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if filters.get("from_date") and filters.get("to_date"):
		shift_f["shift_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		shift_f["shift_date"] = [">=", filters["from_date"]]

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_date"],
	)
	shift_names = [s.name for s in shifts]
	shift_meta = {s.name: s for s in shifts}

	if not shift_names:
		return []

	result = []

	# Resolutions (write-offs, write-ons, carry-forwards)
	for res in frappe.get_all(
		"Shift Resolution",
		filters={
			"parent": ["in", shift_names],
			"resolution_type": ["in", ["Write-off", "Write-on", "Carry Forward"]],
		},
		fields=["parent", "resolution_type", "description", "amount", "qty_l", "approved_by"],
	):
		s = shift_meta.get(res.parent, frappe._dict())
		value = flt(res.amount or res.qty_l or 0, 2)
		result.append(
			{
				"shift_date": s.get("shift_date"),
				"name": res.parent,
				"station": s.get("station"),
				"exception_type": res.resolution_type,
				"description": res.description or "",
				"value": value,
				"approved_by": res.approved_by or "",
				"correction": "",
			}
		)

	# Corrections
	for corr in frappe.get_all(
		"Shift Correction",
		filters={"target_shift": ["in", shift_names], "docstatus": 1},
		fields=["name", "target_shift", "correction_type", "reason"],
	):
		s = shift_meta.get(corr.target_shift, frappe._dict())
		result.append(
			{
				"shift_date": s.get("shift_date"),
				"name": corr.target_shift,
				"station": s.get("station"),
				"exception_type": f"Correction: {corr.correction_type or ''}",
				"description": corr.reason or "",
				"value": 0.0,
				"approved_by": "",
				"correction": corr.name,
			}
		)

	return sorted(result, key=lambda r: (r["shift_date"] or "", r["name"] or ""))
