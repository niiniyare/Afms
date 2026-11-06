"""Open Items — FMS-H06.

Lists items that require action: draft and open Forecourt Shifts,
draft fuel GRNs (Purchase Receipts for fuel), and Shift Corrections
awaiting approval.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Type"), "fieldname": "item_type", "fieldtype": "Data", "width": 140},
		{
			"label": _("Document"),
			"fieldname": "name",
			"fieldtype": "Dynamic Link",
			"options": "doctype_name",
			"width": 180,
		},
		{"label": _("DocType"), "fieldname": "doctype_name", "fieldtype": "Data", "width": 0},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 90},
		{"label": _("Status / Note"), "fieldname": "status", "fieldtype": "Data", "width": 160},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 80},
	]


def _data(filters):
	as_of = today()
	result = []

	station_filter = {}
	if filters.get("station"):
		station_filter["station"] = filters["station"]
	if filters.get("company"):
		station_filter["company"] = filters["company"]

	# Draft / open Forecourt Shifts
	for s in frappe.get_all(
		"Forecourt Shift",
		filters={"docstatus": 0, **station_filter},
		fields=["name", "station", "shift_date", "status"],
		order_by="shift_date asc",
	):
		from frappe.utils import date_diff

		age = date_diff(as_of, s.shift_date or as_of) if s.shift_date else 0
		result.append(
			{
				"item_type": "Draft Shift",
				"name": s.name,
				"doctype_name": "Forecourt Shift",
				"station": s.station,
				"date": s.shift_date,
				"status": s.status or "Draft",
				"age_days": age,
			}
		)

	# Draft fuel GRNs (Purchase Receipt with fuel items)
	# custom_station is the accounting-dimension field; guard against unset-up sites
	_pr_has_station = frappe.get_meta("Purchase Receipt").has_field("custom_station")
	fuel_items = [r.name for r in frappe.get_all("Item", filters={"fms_is_fuel": 1}, fields=["name"])]
	if fuel_items:
		grn_fields = ["name", "posting_date"]
		if _pr_has_station:
			grn_fields.append("custom_station as station")
		grn_filters = {"docstatus": 0, "is_return": 0}
		if station_filter.get("company"):
			grn_filters["company"] = station_filter["company"]
		if _pr_has_station and station_filter.get("station"):
			grn_filters["custom_station"] = station_filter["station"]
		for grn in frappe.get_all(
			"Purchase Receipt",
			filters=grn_filters,
			fields=grn_fields,
			order_by="posting_date asc",
		):
			from frappe.utils import date_diff

			# Only include GRNs that have fuel items
			has_fuel = frappe.db.exists(
				"Purchase Receipt Item",
				{"parent": grn.name, "item_code": ["in", fuel_items]},
			)
			if has_fuel:
				age = date_diff(as_of, grn.posting_date or as_of) if grn.posting_date else 0
				result.append(
					{
						"item_type": "Draft GRN",
						"name": grn.name,
						"doctype_name": "Purchase Receipt",
						"station": grn.get("station"),
						"date": grn.posting_date,
						"status": "Draft",
						"age_days": age,
					}
				)

	# Shift Corrections awaiting approval
	for sc in frappe.get_all(
		"Shift Correction",
		filters={"docstatus": 0, **station_filter},
		fields=["name", "forecourt_shift", "correction_type", "workflow_state"],
		order_by="creation asc",
	):
		shift_date = frappe.db.get_value("Forecourt Shift", sc.forecourt_shift, "shift_date")
		station = frappe.db.get_value("Forecourt Shift", sc.forecourt_shift, "station")
		from frappe.utils import date_diff

		age = date_diff(as_of, shift_date or as_of) if shift_date else 0
		result.append(
			{
				"item_type": "Pending Correction",
				"name": sc.name,
				"doctype_name": "Shift Correction",
				"station": station,
				"date": shift_date,
				"status": sc.workflow_state or "Pending",
				"age_days": age,
			}
		)

	return result
