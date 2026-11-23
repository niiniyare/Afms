"""Nozzle Idle Analysis — MTR-05.

One row per nozzle: last active date, days since last activity, and
aggregate litres dispensed in the filter period. Nozzles with no NLE
activity in the period (or ever) appear with zero litres and a "Idle"
flag. Useful for spotting decommissioned nozzles still on the template
or dormant pumps.

No T-* total row; summary cards show active vs idle count.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, today

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
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
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Nozzle"),
			"fieldname": "nozzle",
			"fieldtype": "Link",
			"options": "Nozzle",
			"width": 110,
		},
		{
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 120,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{"label": _("Last Active"), "fieldname": "last_active", "fieldtype": "Date", "width": 100},
		{
			"label": _("Days Idle"),
			"fieldname": "days_idle",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Shifts (period)"),
			"fieldname": "shift_count",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Litres (period)"),
			"fieldname": "total_litres",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 70},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	perm_f: dict = {}
	if filters.get("company"):
		perm_f["company"] = filters["company"]
	err = apply_station_permission(perm_f, filters)
	if err:
		return [], []

	nozzle_f: dict = {"disabled": 0}
	if filters.get("station"):
		nozzle_f["station"] = filters["station"]
	if "station" in perm_f:
		nozzle_f["station"] = perm_f["station"]
	if filters.get("company"):
		nozzle_f["company"] = filters["company"]

	nozzles = frappe.get_all(
		"Nozzle",
		filters=nozzle_f,
		fields=["name", "station", "tank", "item"],
		order_by="station asc, name asc",
	)
	if not nozzles:
		return [], []

	nozzle_names = [n.name for n in nozzles]

	# Period activity from NLE
	nle_f: dict = {
		"nozzle": ["in", nozzle_names],
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		nle_f["posting_date"] = ["between", [fd, td]]
	elif fd:
		nle_f["posting_date"] = [">=", fd]
	elif td:
		nle_f["posting_date"] = ["<=", td]

	nle_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=nle_f,
		fields=["nozzle", "net_l"],
	)

	# All-time last active date (regardless of period filter)
	all_time_f: dict = {
		"nozzle": ["in", nozzle_names],
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	last_active_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=all_time_f,
		fields=["nozzle", "posting_date"],
		order_by="posting_date desc",
	)

	# Build maps
	period_litres: dict[str, float] = {}
	period_shifts: dict[str, int] = {}
	for r in nle_rows:
		period_litres[r.nozzle] = flt(period_litres.get(r.nozzle, 0.0) + flt(r.net_l, 3), 3)
		period_shifts[r.nozzle] = period_shifts.get(r.nozzle, 0) + 1

	last_active_map: dict[str, date | None] = {}
	for r in last_active_rows:
		if r.nozzle not in last_active_map:
			last_active_map[r.nozzle] = r.posting_date

	as_of = frappe.utils.getdate(td or today())
	min_idle = int(filters.get("min_idle_days") or 0)

	result = []
	idle_count = 0
	active_count = 0

	for n in nozzles:
		last = last_active_map.get(n.name)
		days_idle = (as_of - last).days if last else None
		total_litres = period_litres.get(n.name, 0.0)
		shift_count = period_shifts.get(n.name, 0)
		is_idle = shift_count == 0
		status = _("Idle") if is_idle else _("Active")

		if min_idle and (days_idle is None or days_idle < min_idle):
			continue

		if is_idle:
			idle_count += 1
		else:
			active_count += 1

		result.append(
			{
				"station": n.station,
				"nozzle": n.name,
				"tank": n.tank,
				"item": n.item,
				"last_active": last,
				"days_idle": days_idle,
				"shift_count": shift_count,
				"total_litres": total_litres,
				"status": status,
			}
		)

	summary = [
		summary_card(active_count, _("Active Nozzles"), datatype="Int", indicator="Green"),
		summary_card(
			idle_count, _("Idle Nozzles"), datatype="Int", indicator="Orange" if idle_count else "Green"
		),
	]

	return result, summary
