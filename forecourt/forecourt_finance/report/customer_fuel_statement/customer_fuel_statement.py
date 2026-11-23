"""Customer Fuel Statement — CRD-02.

One row per Shift Credit Sale for a given customer.
Customer filter is required.

T-ADD: qty, amount summed.
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
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
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
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Slip No"),
			"fieldname": "slip_no",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Invoice"),
			"fieldname": "invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 160,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	if not filters.get("customer"):
		frappe.throw(_("Customer is required for Customer Fuel Statement"))

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
		"customer": filters["customer"],
	}
	if filters.get("vehicle"):
		cs_f["vehicle"] = filters["vehicle"]

	cs_rows = frappe.get_all(
		"Shift Credit Sale",
		filters=cs_f,
		fields=[
			"parent",
			"cashier",
			"item",
			"qty",
			"rate",
			"amount",
			"slip_no",
			"sales_invoice",
		],
	)

	result: list[dict] = []
	for cs in cs_rows:
		sh = shift_info.get(cs.parent)
		result.append(
			{
				"posting_date": sh.shift_date if sh else None,
				"station": sh.station if sh else "",
				"shift": cs.parent,
				"cashier": cs.cashier,
				"item": cs.item,
				"qty": flt(cs.qty, 2),
				"rate": flt(cs.rate, 4),
				"amount": flt(cs.amount, 2),
				"slip_no": cs.slip_no or "",
				"invoice": cs.sales_invoice,
			}
		)

	result.sort(key=lambda r: (str(r["posting_date"] or ""), str(r["station"] or "")))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_qty = sum(r["qty"] for r in result)
	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(total_qty, _("Total Litres"), datatype="Float"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
