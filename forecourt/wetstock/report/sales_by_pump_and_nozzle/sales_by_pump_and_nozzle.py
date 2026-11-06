"""Sales by Pump and Nozzle — FMS-H02. Net litres per pump and nozzle from Nozzle Ledger."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Pump"), "fieldname": "dispenser", "fieldtype": "Link", "options": "Pump", "width": 100},
		{"label": _("Nozzle"), "fieldname": "nozzle", "fieldtype": "Link", "options": "Nozzle", "width": 110},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 100},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Gross L"), "fieldname": "gross_l", "fieldtype": "Float", "precision": 3, "width": 100},
		{
			"label": _("Own Use L"),
			"fieldname": "own_use_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{"label": _("Net L"), "fieldname": "net_l", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": _("Revenue"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Drift L"), "fieldname": "drift_l", "fieldtype": "Float", "precision": 3, "width": 90},
		{
			"label": _("Drift %"),
			"fieldname": "drift_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 80,
		},
		{"label": _("Shifts"), "fieldname": "shifts", "fieldtype": "Int", "width": 60},
		{
			"label": _("Avg L/Shift"),
			"fieldname": "avg_l_per_shift",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Station %"),
			"fieldname": "station_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
	]


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	for field in ("company", "station", "item"):
		if filters.get(field):
			f[field] = filters[field]
	if filters.get("dispenser"):
		f["dispenser"] = filters["dispenser"]
	if filters.get("nozzle"):
		f["nozzle"] = filters["nozzle"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		f["posting_date"] = [">=", filters["from_date"]]

	rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=f,
		fields=[
			"dispenser",
			"nozzle",
			"item",
			"station",
			"forecourt_shift",
			"gross_l",
			"own_use_l",
			"net_l",
			"amount",
			"drift_l",
			"drift_pct",
		],
	)

	key_map: dict[tuple, dict] = {}
	for row in rows:
		key = (row.dispenser or "", row.nozzle or "", row.item or "", row.station or "")
		if key not in key_map:
			key_map[key] = {
				"dispenser": row.dispenser,
				"nozzle": row.nozzle,
				"item": row.item,
				"station": row.station,
				"gross_l": 0.0,
				"own_use_l": 0.0,
				"net_l": 0.0,
				"amount": 0.0,
				"drift_l": 0.0,
				"drift_pct": 0.0,
				"_count": 0,
				"_shifts": set(),
			}
		d = key_map[key]
		d["gross_l"] = flt(d["gross_l"] + flt(row.gross_l, 3), 3)
		d["own_use_l"] = flt(d["own_use_l"] + flt(row.own_use_l, 3), 3)
		d["net_l"] = flt(d["net_l"] + flt(row.net_l, 3), 3)
		d["amount"] = flt(d["amount"] + flt(row.amount, 2), 2)
		d["drift_l"] = flt(d["drift_l"] + flt(row.drift_l, 3), 3)
		d["_count"] += 1
		if row.get("forecourt_shift"):
			d["_shifts"].add(row.forecourt_shift)
		d["drift_pct"] = flt(d["drift_l"] / d["gross_l"] * 100, 2) if d["gross_l"] else 0.0

	# station totals for % share
	station_net: dict[str, float] = {}
	for d in key_map.values():
		st = d["station"] or ""
		station_net[st] = flt(station_net.get(st, 0.0) + d["net_l"], 3)

	result = []
	for d in sorted(
		key_map.values(), key=lambda r: (r["station"] or "", r["dispenser"] or "", r["nozzle"] or "")
	):
		shifts = len(d["_shifts"]) or d["_count"]
		d["shifts"] = shifts
		d["avg_l_per_shift"] = flt(d["net_l"] / shifts, 3) if shifts else 0.0
		st_total = station_net.get(d["station"] or "", 0.0)
		d["station_pct"] = flt(d["net_l"] / st_total * 100, 1) if st_total else 0.0
		result.append({k: v for k, v in d.items() if not k.startswith("_")})
	return result
