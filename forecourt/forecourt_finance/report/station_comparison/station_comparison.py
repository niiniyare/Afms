"""Station Comparison — FMS-H06.

Compares key metrics across stations for a period:
litres, revenue, cashier differences, tank variance and shift count.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 140,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 130,
		},
		{"label": _("Shifts"), "fieldname": "shifts", "fieldtype": "Int", "width": 70},
		{"label": _("Litres"), "fieldname": "litres", "fieldtype": "Float", "precision": 3, "width": 110},
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
	date_f: dict = {}
	if filters.get("from_date") and filters.get("to_date"):
		date_f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		date_f["posting_date"] = [">=", filters["from_date"]]

	company_f = {}
	if filters.get("company"):
		company_f["company"] = filters["company"]

	base_f = {"is_cancelled": 0, "superseded_by": ["is", "not set"], **company_f}

	# Sales ledger
	sle_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters={**base_f, **date_f},
		fields=["station", "company", "payment_type", "qty", "amount"],
	)

	# Wetstock ledger (shift variances)
	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={**base_f, "entry_type": "Shift", **date_f},
		fields=["station", "variance_l"],
	)

	# Cashier ledger
	cle_rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters={**base_f, **date_f},
		fields=["station", "difference"],
	)

	# Shift count
	shift_f = {"docstatus": 1, **company_f}
	if filters.get("from_date") and filters.get("to_date"):
		shift_f["shift_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		shift_f["shift_date"] = [">=", filters["from_date"]]
	shift_rows = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["station", "company"],
	)

	station_map: dict[str, dict] = {}

	def _ensure(station: str, company: str) -> dict:
		if station not in station_map:
			station_map[station] = {
				"station": station,
				"company": company,
				"shifts": 0,
				"litres": 0.0,
				"revenue": 0.0,
				"cash": 0.0,
				"mobile": 0.0,
				"card": 0.0,
				"credit": 0.0,
				"tank_var_l": 0.0,
				"cashier_diff": 0.0,
			}
		return station_map[station]

	for row in sle_rows:
		d = _ensure(row.station or "", row.company or "")
		d["litres"] = flt(d["litres"] + flt(row.qty, 3), 3)
		d["revenue"] = flt(d["revenue"] + flt(row.amount, 2), 2)
		pt = (row.payment_type or "").lower()
		if "cash" in pt:
			d["cash"] = flt(d["cash"] + flt(row.amount, 2), 2)
		elif "mobile" in pt:
			d["mobile"] = flt(d["mobile"] + flt(row.amount, 2), 2)
		elif "card" in pt:
			d["card"] = flt(d["card"] + flt(row.amount, 2), 2)
		elif "credit" in pt:
			d["credit"] = flt(d["credit"] + flt(row.amount, 2), 2)

	for row in wle_rows:
		d = _ensure(row.station or "", "")
		d["tank_var_l"] = flt(d["tank_var_l"] + flt(row.variance_l, 3), 3)

	for row in cle_rows:
		d = _ensure(row.station or "", "")
		d["cashier_diff"] = flt(d["cashier_diff"] + flt(row.difference, 2), 2)

	for row in shift_rows:
		d = _ensure(row.station or "", row.company or "")
		d["shifts"] += 1

	return sorted(station_map.values(), key=lambda r: (r["company"] or "", r["station"] or ""))
