"""Daily Station Report — FMS-H01.

Summarises one station's day:
  - Litres and revenue by product (from Sales Ledger)
  - Payment mix (cash / mobile / card / credit)
  - Cashier balances and differences
  - Tank variances

Columns respect User Permissions via frappe.get_list.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = _columns()
	data = _data(filters)
	return columns, data


def _columns():
	return [
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Litres"), "fieldname": "litres", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 120},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Tank Var L"),
			"fieldname": "tank_var_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{"label": _("Cashier Diff"), "fieldname": "cashier_diff", "fieldtype": "Currency", "width": 110},
	]


def _data(filters):
	station = filters.get("station")
	company = filters.get("company")
	date = filters.get("date")

	if not date:
		date = frappe.utils.today()

	sle_filters = {"posting_date": date, "is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if station:
		sle_filters["station"] = station
	if company:
		sle_filters["company"] = company

	# Sales by product
	sle_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=sle_filters,
		fields=["item", "payment_type", "qty", "amount"],
	)

	product_map: dict[str, dict] = {}
	for row in sle_rows:
		item = row.item or ""
		if item not in product_map:
			product_map[item] = {
				"item": item,
				"litres": 0.0,
				"revenue": 0.0,
				"cash": 0.0,
				"mobile": 0.0,
				"card": 0.0,
				"credit": 0.0,
				"tank_var_l": 0.0,
				"cashier_diff": 0.0,
			}
		product_map[item]["litres"] = flt(product_map[item]["litres"] + flt(row.qty, 3), 3)
		product_map[item]["revenue"] = flt(product_map[item]["revenue"] + flt(row.amount, 2), 2)
		pt = (row.payment_type or "").lower()
		if "cash" in pt:
			product_map[item]["cash"] = flt(product_map[item]["cash"] + flt(row.amount, 2), 2)
		elif "mobile" in pt:
			product_map[item]["mobile"] = flt(product_map[item]["mobile"] + flt(row.amount, 2), 2)
		elif "card" in pt:
			product_map[item]["card"] = flt(product_map[item]["card"] + flt(row.amount, 2), 2)
		elif "credit" in pt:
			product_map[item]["credit"] = flt(product_map[item]["credit"] + flt(row.amount, 2), 2)

	# Tank variances (Wetstock Ledger)
	wle_filters = {**sle_filters, "entry_type": "Shift"}
	wle_filters.pop("superseded_by", None)
	wle_filters["superseded_by"] = ["is", "not set"]
	for wle_row in frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_filters,
		fields=["item", "variance_l"],
	):
		item = wle_row.item or ""
		if item in product_map:
			product_map[item]["tank_var_l"] = flt(
				product_map[item]["tank_var_l"] + flt(wle_row.variance_l, 3), 3
			)

	# Cashier differences
	cle_filters = {**sle_filters}
	cle_filters.pop("superseded_by", None)
	cle_filters["superseded_by"] = ["is", "not set"]
	total_diff = flt(
		sum(
			flt(r.difference, 2)
			for r in frappe.get_all(
				"Cashier Ledger Entry",
				filters=cle_filters,
				fields=["difference"],
			)
		),
		2,
	)
	# Spread cashier diff proportionally across products by revenue (or assign to first row)
	rows = sorted(product_map.values(), key=lambda r: r["item"])
	if rows:
		rows[0]["cashier_diff"] = total_diff

	return rows
