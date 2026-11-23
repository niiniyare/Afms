"""Water in Tank — WET-05.

One row per submitted Tank Dip that recorded water (water_mm > 0 or
water_l > 0). Used to track water ingress events and confirm remediation.

No T-* total row; summary shows dip count and highest water reading.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

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
			"label": _("Dipped At"),
			"fieldname": "dipped_at",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Tank Dip"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Tank Dip",
			"width": 150,
		},
		{
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 120,
		},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 110},
		{
			"label": _("Water mm"),
			"fieldname": "water_mm",
			"fieldtype": "Float",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Water L"),
			"fieldname": "water_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 90,
		},
		{
			"label": _("Volume L"),
			"fieldname": "volume_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Dipped By"),
			"fieldname": "dipped_by",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 130,
		},
		{
			"label": _("Witness"),
			"fieldname": "witness",
			"fieldtype": "Link",
			"options": "User",
			"width": 120,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"docstatus": 1}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		f["dipped_at"] = ["between", [fd + " 00:00:00", td + " 23:59:59"]]
	elif fd:
		f["dipped_at"] = [">=", fd + " 00:00:00"]
	elif td:
		f["dipped_at"] = ["<=", td + " 23:59:59"]

	rows = frappe.get_all(
		"Tank Dip",
		filters=f,
		fields=[
			"name",
			"tank",
			"station",
			"dipped_at",
			"purpose",
			"water_mm",
			"water_l",
			"volume_l",
			"dipped_by",
			"witness",
		],
		order_by="dipped_at asc",
	)

	result = [dict(r) for r in rows if flt(r.water_mm) > 0 or flt(r.water_l) > 0]

	max_water = max((flt(r["water_l"]) for r in result), default=0.0)

	summary = [
		summary_card(
			len(result), _("Water Events"), datatype="Int", indicator="Orange" if result else "Green"
		),
		summary_card(flt(max_water, 3), _("Highest Water L"), datatype="Float"),
	]

	return result, summary
