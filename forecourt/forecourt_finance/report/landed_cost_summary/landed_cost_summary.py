"""Landed Cost Summary — PUR-05.

One row per Landed Cost Voucher / expense account combination:
total landed costs allocated to fuel Purchase Invoices, broken down
by expense head.

T-ADD: amount summed.
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
			"label": _("LCV"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Landed Cost Voucher",
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
			"fieldtype": "Data",
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
			"label": _("Expense Account"),
			"fieldname": "expense_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 160,
		},
		{
			"label": _("Description"),
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Purchase Invoice"),
			"fieldname": "receipt_document",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
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

	# Landed Cost Vouchers submitted
	lcv_f: dict = {"docstatus": 1}
	if company:
		lcv_f["company"] = company
	apply_date_filter(lcv_f, filters)

	lcv_rows = frappe.get_all(
		"Landed Cost Voucher",
		filters=lcv_f,
		fields=["name", "posting_date"],
		order_by="posting_date asc",
	)
	if not lcv_rows:
		return [], []

	lcv_names = [lcv.name for lcv in lcv_rows]
	lcv_dates = {lcv.name: lcv.posting_date for lcv in lcv_rows}

	# Receipt links (Purchase Invoice)
	receipt_rows = frappe.get_all(
		"Landed Cost Purchase Receipt",
		filters={
			"parent": ["in", lcv_names],
			"receipt_document_type": "Purchase Invoice",
		},
		fields=["parent", "receipt_document"],
	)

	# Build PI → supplier map
	pi_names = list({r.receipt_document for r in receipt_rows if r.receipt_document})
	pi_supplier: dict[str, str] = {}
	pi_item: dict[str, str] = {}
	if pi_names:
		pis = frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", pi_names]},
			fields=["name", "supplier"],
		)
		pi_supplier = {pi.name: pi.supplier for pi in pis}
		pi_items = frappe.get_all(
			"Purchase Invoice Item",
			filters={"parent": ["in", pi_names]},
			fields=["parent", "item_code"],
		)
		for it in pi_items:
			pi_item.setdefault(it.parent, it.item_code)

	# Map LCV → (receipt_document, supplier, item)
	lcv_receipt: dict[str, list[tuple]] = {}
	for rr in receipt_rows:
		lcv_receipt.setdefault(rr.parent, []).append(
			(
				rr.receipt_document,
				pi_supplier.get(rr.receipt_document, ""),
				pi_item.get(rr.receipt_document, ""),
			)
		)

	# Tax and charge lines
	tax_rows = frappe.get_all(
		"Landed Cost Taxes and Charges",
		filters={"parent": ["in", lcv_names]},
		fields=["parent", "expense_account", "description", "amount"],
	)

	# Apply filters
	supplier_f = filters.get("supplier")
	item_f = filters.get("item")
	expense_f = filters.get("expense_account")

	result: list[dict] = []
	for tax in tax_rows:
		if expense_f and tax.expense_account != expense_f:
			continue
		for receipt_doc, supplier, item in lcv_receipt.get(tax.parent, []):
			if supplier_f and supplier != supplier_f:
				continue
			if item_f and item != item_f:
				continue
			result.append(
				{
					"name": tax.parent,
					"posting_date": lcv_dates.get(tax.parent),
					"supplier": supplier,
					"item": item,
					"expense_account": tax.expense_account,
					"description": tax.description or "",
					"amount": flt(tax.amount, 2),
					"receipt_document": receipt_doc,
				}
			)

	result.sort(key=lambda r: (str(r["posting_date"]), str(r["name"])))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("LCV Lines"), datatype="Int"),
		summary_card(total_amount, _("Total Landed Costs"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
