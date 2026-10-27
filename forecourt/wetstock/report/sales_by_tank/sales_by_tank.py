"""Sales by Tank — FMS-H02. Litres and revenue per tank from Nozzle Ledger and Sales Ledger."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Tank"), "fieldname": "tank", "fieldtype": "Link", "options": "Fuel Tank", "width": 120},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 110},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Litres"), "fieldname": "net_l", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": _("Revenue"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Var %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 80,
		},
	]


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "tank", "item"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	# Litres from Nozzle Ledger (gross minus own use)
	nle_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters={**f},
		fields=["tank", "item", "station", "net_l", "amount"],
	)

	# Variance from Wetstock Ledger (Shift entries)
	wle_f = {k: v for k, v in f.items()}
	wle_f["entry_type"] = "Shift"
	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=["tank", "item", "station", "variance_l", "sales_l"],
	)

	key_map: dict[tuple, dict] = {}
	for row in nle_rows:
		key = (row.tank or "", row.item or "", row.station or "")
		if key not in key_map:
			key_map[key] = {
				"tank": row.tank,
				"item": row.item,
				"station": row.station,
				"net_l": 0.0,
				"amount": 0.0,
				"variance_l": 0.0,
				"_sales_l": 0.0,
			}
		d = key_map[key]
		d["net_l"] = flt(d["net_l"] + flt(row.net_l, 3), 3)
		d["amount"] = flt(d["amount"] + flt(row.amount, 2), 2)

	for row in wle_rows:
		key = (row.tank or "", row.item or "", row.station or "")
		if key not in key_map:
			key_map[key] = {
				"tank": row.tank,
				"item": row.item,
				"station": row.station,
				"net_l": 0.0,
				"amount": 0.0,
				"variance_l": 0.0,
				"_sales_l": 0.0,
			}
		d = key_map[key]
		d["variance_l"] = flt(d["variance_l"] + flt(row.variance_l, 3), 3)
		d["_sales_l"] = flt(d["_sales_l"] + flt(row.sales_l, 3), 3)

	result = []
	for d in sorted(key_map.values(), key=lambda r: (r["station"] or "", r["tank"] or "", r["item"] or "")):
		variance_pct = flt(d["variance_l"] / d["_sales_l"] * 100, 2) if d["_sales_l"] else 0.0
		result.append(
			{
				"tank": d["tank"],
				"item": d["item"],
				"station": d["station"],
				"net_l": d["net_l"],
				"amount": d["amount"],
				"variance_l": d["variance_l"],
				"variance_pct": variance_pct,
			}
		)
	return result
