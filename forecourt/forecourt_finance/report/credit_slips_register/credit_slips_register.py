"""Credit Slips Register — FMS-H05.

Lists credit sales per shift with slip numbers and gap detection.
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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
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
		{"label": _("Slip No"), "fieldname": "slip_no", "fieldtype": "Data", "width": 90},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"label": _("Vehicle"),
			"fieldname": "vehicle",
			"fieldtype": "Link",
			"options": "Customer Vehicle",
			"width": 110,
		},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("Qty L"), "fieldname": "qty", "fieldtype": "Float", "precision": 3, "width": 90},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Gap?"), "fieldname": "gap_flag", "fieldtype": "Data", "width": 60},
	]


def _data(filters):
	# Pull credit sale rows from submitted Forecourt Shifts
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
		order_by="shift_date asc",
	)

	result = []
	for shift in shifts:
		credit_sales = frappe.get_all(
			"Shift Credit Sale",
			filters={"parent": shift.name},
			fields=["slip_no", "customer", "vehicle", "item", "qty", "amount"],
			order_by="slip_no asc",
		)
		prev_slip = None
		for cs in credit_sales:
			gap_flag = ""
			slip = cs.slip_no or ""
			if prev_slip and slip:
				try:
					if int(slip) - int(prev_slip) > 1:
						gap_flag = "GAP"
				except (ValueError, TypeError):
					pass
			prev_slip = slip
			result.append(
				{
					"posting_date": shift.shift_date,
					"forecourt_shift": shift.name,
					"station": shift.station,
					"slip_no": slip,
					"customer": cs.customer,
					"vehicle": cs.vehicle,
					"item": cs.item,
					"qty": flt(cs.qty, 3),
					"amount": flt(cs.amount, 2),
					"gap_flag": gap_flag,
				}
			)
	return result
