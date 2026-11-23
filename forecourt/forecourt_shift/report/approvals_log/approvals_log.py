"""Approvals Log — CTL-02.

Every approval action on Forecourt Shift, Fuel Price Change, and Shift Correction.

T-REG: count approvals.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
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
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Document Type"),
			"fieldname": "document_type",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Document"),
			"fieldname": "document",
			"fieldtype": "Data",
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
			"label": _("Action By"),
			"fieldname": "action_by",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
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

	doc_type_filter = filters.get("document_type")
	result: list[dict] = []

	# Forecourt Shift approvals
	if not doc_type_filter or doc_type_filter == "Forecourt Shift":
		shift_f: dict = {"docstatus": 1, "approval_state": "Approved"}
		if filters.get("company"):
			shift_f["company"] = filters["company"]
		if station_filter:
			shift_f["station"] = station_filter
		apply_shift_date_filter(shift_f, filters)
		shifts = frappe.get_all(
			"Forecourt Shift",
			filters=shift_f,
			fields=["name", "station", "shift_date", "approved_by", "approval_state"],
		)
		for s in shifts:
			result.append(
				{
					"posting_date": s.shift_date,
					"document_type": _("Forecourt Shift"),
					"document": s.name,
					"station": s.station,
					"action_by": s.approved_by or "",
					"status": s.approval_state or "",
				}
			)

	# Fuel Price Change approvals
	if not doc_type_filter or doc_type_filter == "Fuel Price Change":
		fpc_f: dict = {"docstatus": 1}
		if filters.get("company"):
			fpc_f["company"] = filters["company"]
		if station_filter:
			fpc_f["station"] = station_filter
		apply_date_filter(fpc_f, filters, date_field="effective_at")
		fpcs = frappe.get_all(
			"Fuel Price Change",
			filters=fpc_f,
			fields=["name", "station", "effective_at", "modified_by"],
		)
		for fpc in fpcs:
			result.append(
				{
					"posting_date": fpc.effective_at,
					"document_type": _("Fuel Price Change"),
					"document": fpc.name,
					"station": fpc.station,
					"action_by": fpc.modified_by or "",
					"status": _("Submitted"),
				}
			)

	# Shift Correction approvals
	if not doc_type_filter or doc_type_filter == "Shift Correction":
		cor_f: dict = {"docstatus": 1}
		if filters.get("company"):
			cor_f["company"] = filters["company"]
		if station_filter:
			cor_f["station"] = station_filter
		apply_date_filter(cor_f, filters)
		cors = frappe.get_all(
			"Shift Correction",
			filters=cor_f,
			fields=["name", "station", "creation", "approved_by", "approval_state"],
		)
		for c in cors:
			result.append(
				{
					"posting_date": c.creation,
					"document_type": _("Shift Correction"),
					"document": c.name,
					"station": c.station,
					"action_by": c.approved_by or "",
					"status": c.approval_state or "",
				}
			)

	result.sort(key=lambda r: (str(r["posting_date"]), str(r["document_type"])))

	cols = _columns()
	total = total_row_reg(result, cols, count_label="document") if result else {}

	summary = [
		summary_card(len(result), _("Approvals"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
