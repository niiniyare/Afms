"""Delivery Accuracy — WET-06.

One row per WLE Delivery entry: invoiced vs dipped quantity, variance
and variance %. Used to hold suppliers and transporters accountable for
short or over deliveries.

T-ADD totals on invoiced_l, receipt_l, delivery_variance_l.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_add,
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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 120,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130,
		},
		{
			"label": _("Transporter"),
			"fieldname": "transporter",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130,
		},
		{
			"label": _("Invoiced L"),
			"fieldname": "invoiced_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
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
			"label": _("Variance %"),
			"fieldname": "variance_pct",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("GRN"),
			"fieldname": "voucher_no",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 150,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"entry_type": "Delivery",
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	if filters.get("supplier"):
		f["supplier"] = filters["supplier"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"posting_date",
			"station",
			"tank",
			"item",
			"supplier",
			"transporter",
			"invoiced_l",
			"receipt_l",
			"delivery_variance_l",
			"voucher_no",
		],
		order_by="posting_date asc, station asc",
	)

	result = []
	for r in rows:
		inv = flt(r.invoiced_l, 3)
		rec = flt(r.receipt_l, 3)
		var = flt(r.delivery_variance_l, 3)
		pct = flt(var / inv * 100, 2) if inv else 0.0
		result.append(
			{
				"posting_date": r.posting_date,
				"station": r.station,
				"tank": r.tank,
				"item": r.item,
				"supplier": r.supplier,
				"transporter": r.transporter,
				"invoiced_l": inv,
				"receipt_l": rec,
				"delivery_variance_l": var,
				"variance_pct": pct,
				"voucher_no": r.voucher_no,
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_invoiced = sum(r["invoiced_l"] for r in result)
	total_variance = sum(r["delivery_variance_l"] for r in result)

	summary = [
		summary_card(len(result), _("Deliveries"), datatype="Int"),
		summary_card(flt(total_invoiced, 3), _("Total Invoiced L"), datatype="Float"),
		summary_card(
			flt(total_variance, 3),
			_("Total Variance L"),
			datatype="Float",
			indicator="Orange" if abs(total_variance) > 0 else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
