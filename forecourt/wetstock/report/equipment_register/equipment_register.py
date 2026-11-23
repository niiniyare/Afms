"""Equipment Register — EQP-01.

Master list of all nozzles, pumps, tanks and calibration charts
for a station. One row per nozzle with its parent pump, tank and product.
No date filter — this is a snapshot of the current equipment.

T-REG: count rows.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_reg,
)


def execute(filters: dict | None = None):
	filters = filters or {}
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
			"width": 140,
		},
		{
			"label": _("Pump"),
			"fieldname": "pump",
			"fieldtype": "Link",
			"options": "Pump",
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
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Last Reading"),
			"fieldname": "last_ecash",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Last Shift"),
			"fieldname": "last_reading_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Ecash Max"),
			"fieldname": "ecash_max",
			"fieldtype": "Float",
			"precision": 0,
			"width": 90,
		},
		{
			"label": _("Has Calibration"),
			"fieldname": "has_calibration",
			"fieldtype": "Check",
			"width": 110,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	if filters.get("station"):
		f_perm["station"] = filters["station"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []
	station_filter = f_perm.get("station")

	nozzle_f: dict = {}
	if station_filter:
		nozzle_f["station"] = station_filter
	if filters.get("status"):
		nozzle_f["status"] = filters["status"]
	if filters.get("item"):
		nozzle_f["item"] = filters["item"]

	nozzles = frappe.get_all(
		"Nozzle",
		filters=nozzle_f,
		fields=[
			"name",
			"station",
			"pump",
			"tank",
			"item",
			"status",
			"last_ecash",
			"last_reading_shift",
			"ecash_max",
		],
		order_by="station asc, pump asc, name asc",
	)
	if not nozzles:
		return [], []

	# Check which tanks have a calibration chart
	tank_names = list({n.tank for n in nozzles if n.tank})
	calibrated: set[str] = set()
	if tank_names:
		charts = frappe.get_all(
			"Tank Calibration Chart",
			filters={"tank": ["in", tank_names]},
			fields=["tank"],
		)
		calibrated = {c.tank for c in charts}

	result: list[dict] = []
	for noz in nozzles:
		result.append(
			{
				"station": noz.station,
				"nozzle": noz.name,
				"pump": noz.pump,
				"tank": noz.tank,
				"item": noz.item,
				"status": noz.status,
				"last_ecash": flt(noz.last_ecash, 2),
				"last_reading_shift": noz.last_reading_shift,
				"ecash_max": flt(noz.ecash_max, 0),
				"has_calibration": 1 if noz.tank and noz.tank in calibrated else 0,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="nozzle") if result else {}

	active = sum(1 for r in result if r["status"] == "Active")
	summary = [
		summary_card(len(result), _("Nozzles"), datatype="Int"),
		summary_card(active, _("Active"), datatype="Int", indicator="Green"),
	]

	if total:
		result.append(total)

	return result, summary
