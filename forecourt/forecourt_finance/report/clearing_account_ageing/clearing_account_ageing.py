"""Clearing Account Ageing — FMS-H05.

Mobile money and card Payment Entries not yet reconciled against bank statements,
grouped by provider and aged in 0-7, 8-30, 31-60, 60+ day buckets.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import date_diff, flt, today


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Payment Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Payment Entry",
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
			"label": _("Mode"),
			"fieldname": "mode_of_payment",
			"fieldtype": "Link",
			"options": "Mode of Payment",
			"width": 120,
		},
		{"label": _("Reference"), "fieldname": "reference_no", "fieldtype": "Data", "width": 140},
		{"label": _("Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 80},
		{"label": _("Bucket"), "fieldname": "bucket", "fieldtype": "Data", "width": 70},
	]


def _data(filters):
	as_of = filters.get("date") or today()
	f = {"docstatus": 1, "clearance_date": ["is", "not set"]}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["custom_station"] = filters["station"]
	if filters.get("mode_of_payment"):
		f["mode_of_payment"] = filters["mode_of_payment"]

	# Only Mobile Money and Card type entries (non-cash clearing)
	f["payment_type"] = "Receive"
	rows = frappe.get_all(
		"Payment Entry",
		filters=f,
		fields=[
			"name",
			"posting_date",
			"custom_station as station",
			"mode_of_payment",
			"reference_no",
			"paid_amount",
		],
		order_by="posting_date asc",
	)

	result = []
	for row in rows:
		age = date_diff(as_of, row.posting_date or as_of)
		if age <= 7:
			bucket = "0-7"
		elif age <= 30:
			bucket = "8-30"
		elif age <= 60:
			bucket = "31-60"
		else:
			bucket = "60+"
		result.append(
			{
				"posting_date": row.posting_date,
				"name": row.name,
				"station": row.station,
				"mode_of_payment": row.mode_of_payment,
				"reference_no": row.reference_no,
				"paid_amount": flt(row.paid_amount, 2),
				"age_days": age,
				"bucket": bucket,
			}
		)
	return result
