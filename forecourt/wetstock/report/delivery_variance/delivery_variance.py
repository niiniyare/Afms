"""Delivery Variance — FMS-H04. Variance between GRN quantity and delivery dip per tank."""

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
		{"label": _("GRN"), "fieldname": "voucher_no", "fieldtype": "Data", "width": 140},
		{"label": _("Tank"), "fieldname": "tank", "fieldtype": "Link", "options": "Fuel Tank", "width": 120},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 110},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Received L"),
			"fieldname": "receipt_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Variance L"),
			"fieldname": "delivery_variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130,
		},
	]


def _data(filters):
	f = {"entry_type": "Delivery", "is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	if filters.get("supplier"):
		f["supplier"] = filters["supplier"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"posting_date",
			"voucher_no",
			"tank",
			"item",
			"station",
			"receipt_l",
			"delivery_variance_l",
			"supplier",
		],
		order_by="posting_date desc",
	)

	return [
		{
			"posting_date": r.posting_date,
			"voucher_no": r.voucher_no,
			"tank": r.tank,
			"item": r.item,
			"station": r.station,
			"receipt_l": flt(r.receipt_l, 3),
			"delivery_variance_l": flt(r.delivery_variance_l, 3),
			"supplier": r.supplier,
		}
		for r in rows
	]
