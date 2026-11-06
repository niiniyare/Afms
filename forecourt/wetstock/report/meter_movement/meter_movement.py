"""Meter Movement — MTR-01.

One row per nozzle ledger entry: meter readings, deltas, basis and drift.
Useful for tracking meter trends and detecting manipulation over time.
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
			"width": 120,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Nozzle"),
			"fieldname": "nozzle",
			"fieldtype": "Link",
			"options": "Nozzle",
			"width": 90,
		},
		{
			"label": _("Dispenser"),
			"fieldname": "dispenser",
			"fieldtype": "Link",
			"options": "Pump",
			"width": 100,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100,
		},
		{
			"label": _("Opening E-Cash"),
			"fieldname": "opening_elec_cash",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Closing E-Cash"),
			"fieldname": "closing_elec_cash",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("E-Cash Δ"),
			"fieldname": "ecash_delta",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Opening E-Vol"),
			"fieldname": "opening_elec_meter",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Closing E-Vol"),
			"fieldname": "closing_elec_meter",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("E-Vol Δ"),
			"fieldname": "evol_delta",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Basis"),
			"fieldname": "basis_meter",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": _("Net L"),
			"fieldname": "net_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Drift L"),
			"fieldname": "drift_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 80,
		},
		{
			"label": _("Drift %"),
			"fieldname": "drift_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 70,
		},
	]


def _data(filters: dict) -> list[dict]:
	f: dict = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "nozzle", "dispenser", "item"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	return frappe.get_all(
		"Nozzle Ledger Entry",
		filters=f,
		fields=[
			"station",
			"posting_date",
			"forecourt_shift",
			"nozzle",
			"dispenser",
			"item",
			"opening_elec_cash",
			"closing_elec_cash",
			"ecash_delta",
			"opening_elec_meter",
			"closing_elec_meter",
			"evol_delta",
			"basis_meter",
			"net_l",
			"drift_l",
			"drift_pct",
		],
		order_by="posting_date asc, station asc, nozzle asc",
	)
