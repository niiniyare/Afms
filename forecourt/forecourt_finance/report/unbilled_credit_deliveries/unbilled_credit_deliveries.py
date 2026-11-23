"""Unbilled Credit Deliveries — CRD-05.

Shift Credit Sale rows where neither sales_invoice nor delivery_note
has been set — i.e. not yet billed to the customer.

T-REG: count rows.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

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
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
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
			"label": _("Qty (L)"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Days Outstanding"),
			"fieldname": "days_outstanding",
			"fieldtype": "Int",
			"width": 120,
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

	shift_f: dict = {
		"docstatus": 1,
		"is_cancelled": 0,
	}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if station_filter:
		shift_f["station"] = station_filter
	apply_date_filter(shift_f, filters, date_field="shift_date")

	shift_rows = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_date"],
	)
	if not shift_rows:
		return [], []

	shift_names = [s.name for s in shift_rows]
	shift_info = {s.name: s for s in shift_rows}

	cs_f: dict = {
		"parent": ["in", shift_names],
		"sales_invoice": ["is", "not set"],
		"delivery_note": ["is", "not set"],
	}
	if filters.get("customer"):
		cs_f["customer"] = filters["customer"]

	cs_rows = frappe.get_all(
		"Shift Credit Sale",
		filters=cs_f,
		fields=["parent", "customer", "vehicle", "item", "qty", "amount"],
	)

	today = getdate(nowdate())
	result: list[dict] = []
	for cs in cs_rows:
		sh = shift_info.get(cs.parent)
		posting = getdate(sh.shift_date) if sh and sh.shift_date else today
		days_outstanding = (today - posting).days
		result.append(
			{
				"posting_date": sh.shift_date if sh else None,
				"station": sh.station if sh else "",
				"shift": cs.parent,
				"customer": cs.customer,
				"vehicle": cs.vehicle,
				"item": cs.item,
				"qty": flt(cs.qty, 2),
				"amount": flt(cs.amount, 2),
				"days_outstanding": days_outstanding,
			}
		)

	result.sort(key=lambda r: (-(r["days_outstanding"] or 0), str(r["posting_date"] or "")))

	cols = _columns()
	total = total_row_reg(result, cols, count_label="shift") if result else {}

	total_qty = sum(r["qty"] for r in result)
	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("Unbilled Lines"), datatype="Int"),
		summary_card(total_qty, _("Total Litres"), datatype="Float"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
