"""Cashier Statement — FMS-H05.

Per cashier per period: fuel sold, items sold, collections, expected, difference.
Difference at end = running balance charged to Staff Shortage Receivable.
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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Fuel L"), "fieldname": "fuel_l", "fieldtype": "Float", "precision": 3, "width": 90},
		{"label": _("Fuel Amt"), "fieldname": "fuel_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Items"), "fieldname": "item_amount", "fieldtype": "Currency", "width": 100},
		{"label": _("Cash"), "fieldname": "cash", "fieldtype": "Currency", "width": 100},
		{"label": _("Mobile"), "fieldname": "mobile", "fieldtype": "Currency", "width": 100},
		{"label": _("Card"), "fieldname": "card", "fieldtype": "Currency", "width": 100},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 100},
		{"label": _("Expected"), "fieldname": "expected", "fieldtype": "Currency", "width": 110},
		{"label": _("Accounted"), "fieldname": "accounted", "fieldtype": "Currency", "width": 110},
		{"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "width": 110},
	]


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("cashier"):
		f["cashier"] = filters["cashier"]
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=f,
		fields=[
			"posting_date",
			"forecourt_shift",
			"station",
			"cashier",
			"fuel_l",
			"fuel_amount",
			"item_amount",
			"cash",
			"mobile",
			"card",
			"credit",
			"expected",
			"accounted",
			"difference",
		],
		order_by="posting_date asc, forecourt_shift asc",
	)

	return [
		{
			"posting_date": r.posting_date,
			"forecourt_shift": r.forecourt_shift,
			"station": r.station,
			"fuel_l": flt(r.fuel_l, 3),
			"fuel_amount": flt(r.fuel_amount, 2),
			"item_amount": flt(r.item_amount, 2),
			"cash": flt(r.cash, 2),
			"mobile": flt(r.mobile, 2),
			"card": flt(r.card, 2),
			"credit": flt(r.credit, 2),
			"expected": flt(r.expected, 2),
			"accounted": flt(r.accounted, 2),
			"difference": flt(r.difference, 2),
		}
		for r in rows
	]
