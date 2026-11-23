"""Fuel Purchase Register — PUR-01.

One row per submitted Purchase Invoice item (fuel), showing supplier,
product, quantity, net amount, tax amount, total and payment status.

T-ADD: qty, net_amount, tax_amount, total_amount summed.
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
			"label": _("Invoice"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 160,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
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
			"width": 100,
		},
		{
			"label": _("Net Amount"),
			"fieldname": "net_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Tax Amount"),
			"fieldname": "tax_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Total"),
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Payment Status"),
			"fieldname": "payment_status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("GRN"),
			"fieldname": "grn",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 160,
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
	pi_f: dict = {"docstatus": 1}
	if company:
		pi_f["company"] = company
	if filters.get("supplier"):
		pi_f["supplier"] = filters["supplier"]
	apply_date_filter(pi_f, filters)

	pi_rows = frappe.get_all(
		"Purchase Invoice",
		filters=pi_f,
		fields=[
			"name",
			"supplier",
			"posting_date",
			"net_total",
			"total_taxes_and_charges",
			"grand_total",
			"outstanding_amount",
		],
		order_by="posting_date asc",
	)
	if not pi_rows:
		return [], []

	pi_names = [pi.name for pi in pi_rows]
	pi_map = {pi.name: pi for pi in pi_rows}

	item_f: dict = {"parent": ["in", pi_names]}
	if filters.get("item"):
		item_f["item_code"] = filters["item"]

	pi_items = frappe.get_all(
		"Purchase Invoice Item",
		filters=item_f,
		fields=["parent", "item_code", "qty", "net_amount", "purchase_receipt"],
	)

	# Tax per item proportional to net_amount
	result: list[dict] = []
	for pii in pi_items:
		pi = pi_map.get(pii.parent)
		if not pi:
			continue
		net = flt(pii.net_amount, 2)
		# Proportional tax
		pi_net = flt(pi.net_total, 2)
		pi_tax = flt(pi.total_taxes_and_charges, 2)
		tax = flt((net / pi_net * pi_tax) if pi_net else 0, 2)
		total = flt(net + tax, 2)
		outstanding = flt(pi.outstanding_amount, 2)
		payment_status = _("Paid") if outstanding <= 0 else _("Unpaid ({0})").format(outstanding)
		result.append(
			{
				"posting_date": pi.posting_date,
				"name": pi.name,
				"supplier": pi.supplier,
				"item": pii.item_code,
				"qty": flt(pii.qty, 2),
				"net_amount": net,
				"tax_amount": tax,
				"total_amount": total,
				"payment_status": payment_status,
				"grn": pii.purchase_receipt,
			}
		)

	result.sort(key=lambda r: (str(r["posting_date"]), str(r["name"])))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_qty = sum(r["qty"] for r in result)
	total_net = sum(r["net_amount"] for r in result)
	total_total = sum(r["total_amount"] for r in result)
	summary = [
		summary_card(total_qty, _("Total Litres"), datatype="Float"),
		summary_card(total_net, _("Net Amount"), datatype="Currency"),
		summary_card(total_total, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
