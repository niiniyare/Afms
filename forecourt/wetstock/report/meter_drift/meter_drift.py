"""Meter Drift — FMS-H04. Drift between meters per nozzle per shift from Nozzle Ledger."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import apply_date_filter, apply_station_permission, validate_date_range


def execute(filters=None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
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
		{"label": _("Nozzle"), "fieldname": "nozzle", "fieldtype": "Link", "options": "Nozzle", "width": 110},
		{"label": _("Pump"), "fieldname": "dispenser", "fieldtype": "Link", "options": "Pump", "width": 100},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 100},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Basis"), "fieldname": "basis_meter", "fieldtype": "Data", "width": 90},
		{"label": _("Gross L"), "fieldname": "gross_l", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": _("Drift L"), "fieldname": "drift_l", "fieldtype": "Float", "precision": 3, "width": 90},
		{
			"label": _("Drift %"),
			"fieldname": "drift_pct",
			"fieldtype": "Percent",
			"precision": 3,
			"width": 80,
		},
		{"label": _("Reason"), "fieldname": "drift_reason", "fieldtype": "Data", "width": 140},
	]


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("nozzle"):
		f["nozzle"] = filters["nozzle"]
	if filters.get("dispenser"):
		f["dispenser"] = filters["dispenser"]
	apply_date_filter(f, filters)
	if filters.get("has_drift"):
		f["drift_l"] = ["!=", 0]
	err = apply_station_permission(f, filters)
	if err:
		return []

	rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=f,
		fields=[
			"posting_date",
			"forecourt_shift",
			"nozzle",
			"dispenser",
			"item",
			"station",
			"basis_meter",
			"gross_l",
			"drift_l",
			"drift_pct",
			"drift_reason",
		],
		order_by="posting_date desc, nozzle asc",
	)

	return [
		{
			"posting_date": r.posting_date,
			"forecourt_shift": r.forecourt_shift,
			"nozzle": r.nozzle,
			"dispenser": r.dispenser,
			"item": r.item,
			"station": r.station,
			"basis_meter": r.basis_meter or "",
			"gross_l": flt(r.gross_l, 3),
			"drift_l": flt(r.drift_l, 3),
			"drift_pct": flt(r.drift_pct, 3),
			"drift_reason": r.drift_reason or "",
		}
		for r in rows
	]
