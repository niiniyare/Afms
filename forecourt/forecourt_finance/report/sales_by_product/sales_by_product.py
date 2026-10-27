"""Sales by Product — FMS-H02. Totals from Sales Ledger Entry."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 140},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Litres"), "fieldname": "qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("Revenue"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{"label": _("Basis"), "fieldname": "basis", "fieldtype": "Data", "width": 80},
	]


def _data(filters):
	f = _base_filters(filters)
	rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=f,
		fields=["item", "station", "payment_type", "basis", "qty", "amount"],
	)

	key_map: dict[tuple, dict] = {}
	for row in rows:
		key = (row.item or "", row.station or "")
		if key not in key_map:
			key_map[key] = {
				"item": row.item,
				"station": row.station,
				"qty": 0.0,
				"amount": 0.0,
				"cash": 0.0,
				"mobile": 0.0,
				"card": 0.0,
				"credit": 0.0,
				"basis": row.basis or "",
			}
		d = key_map[key]
		d["qty"] = flt(d["qty"] + flt(row.qty, 3), 3)
		d["amount"] = flt(d["amount"] + flt(row.amount, 2), 2)
		pt = (row.payment_type or "").lower()
		if "cash" in pt:
			d["cash"] = flt(d["cash"] + flt(row.amount, 2), 2)
		elif "mobile" in pt:
			d["mobile"] = flt(d["mobile"] + flt(row.amount, 2), 2)
		elif "card" in pt:
			d["card"] = flt(d["card"] + flt(row.amount, 2), 2)
		elif "credit" in pt:
			d["credit"] = flt(d["credit"] + flt(row.amount, 2), 2)

	return sorted(key_map.values(), key=lambda r: (r["station"] or "", r["item"] or ""))


def _base_filters(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "item"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]
	if filters.get("to_date"):
		if "posting_date" in f:
			f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
		else:
			f["posting_date"] = ["<=", filters["to_date"]]
	return f
