"""Supplier Advances — PUR-03.

Advance payments made to fuel suppliers (Payment Entry, payment_type Advance,
party_type Supplier) that have not yet been allocated to a Purchase Invoice.
Shows open advance balance per supplier.

T-ADD: paid_amount, allocated_amount, unallocated summed.
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
			"label": _("Payment Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 160,
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
		},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Allocated"),
			"fieldname": "allocated_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Unallocated"),
			"fieldname": "unallocated",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Reference"),
			"fieldname": "reference_no",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []

	company = filters.get("company")
	pe_f: dict = {
		"docstatus": 1,
		"payment_type": "Pay",
		"party_type": "Supplier",
	}
	if company:
		pe_f["company"] = company
	if filters.get("supplier"):
		pe_f["party"] = filters["supplier"]
	apply_date_filter(pe_f, filters)

	pe_rows = frappe.get_all(
		"Payment Entry",
		filters=pe_f,
		fields=[
			"name",
			"posting_date",
			"party",
			"paid_amount",
			"unallocated_amount",
			"reference_no",
		],
		order_by="posting_date asc",
	)
	if not pe_rows:
		return [], []

	result: list[dict] = []
	for pe in pe_rows:
		paid = flt(pe.paid_amount, 2)
		unalloc = flt(pe.unallocated_amount, 2)
		alloc = flt(paid - unalloc, 2)
		result.append(
			{
				"name": pe.name,
				"posting_date": pe.posting_date,
				"supplier": pe.party,
				"paid_amount": paid,
				"allocated_amount": alloc,
				"unallocated": unalloc,
				"reference_no": pe.reference_no or "",
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_paid = sum(r["paid_amount"] for r in result)
	total_unalloc = sum(r["unallocated"] for r in result)
	summary = [
		summary_card(total_paid, _("Total Advances"), datatype="Currency"),
		summary_card(total_unalloc, _("Unallocated"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
