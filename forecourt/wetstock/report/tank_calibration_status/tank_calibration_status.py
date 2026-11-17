"""Tank Calibration Status — WET-07.

One row per active Fuel Tank: whether a calibration chart exists, how
many chart points it has, and when it was last updated. Used to ensure
all tanks have a valid chart before going live.

No T-* total row; summary shows charted vs uncharted count.
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
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
			"label": _("Tank"),
			"fieldname": "tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 150,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Chart"),
			"fieldname": "chart",
			"fieldtype": "Link",
			"options": "Tank Calibration Chart",
			"width": 160,
		},
		{"label": _("Points"), "fieldname": "points", "fieldtype": "Int", "width": 70},
		{
			"label": _("Max Volume L"),
			"fieldname": "max_volume_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 110,
		},
		{"label": _("Valid From"), "fieldname": "valid_from", "fieldtype": "Date", "width": 100},
		{"label": _("Source"), "fieldname": "source", "fieldtype": "Data", "width": 150},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"disabled": 0}
	if filters.get("company"):
		f["company"] = filters["company"]
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	tanks = frappe.get_all(
		"Fuel Tank",
		filters=f,
		fields=["name", "station", "item"],
		order_by="station asc, name asc",
	)
	if not tanks:
		return [], []

	tank_names = [t.name for t in tanks]

	charts = frappe.get_all(
		"Tank Calibration Chart",
		filters={"tank": ["in", tank_names]},
		fields=["name", "tank", "valid_from", "source", "max_volume_l"],
		order_by="valid_from desc",
	)

	# Latest chart per tank + count rows
	chart_map: dict[str, dict] = {}
	for c in charts:
		if c.tank not in chart_map:
			chart_map[c.tank] = dict(c)
			chart_map[c.tank]["points"] = 0

	# Count rows per chart
	if chart_map:
		chart_names = [v["name"] for v in chart_map.values()]
		row_counts = frappe.db.get_all(
			"Tank Calibration Row",
			filters={"parent": ["in", chart_names], "parenttype": "Tank Calibration Chart"},
			fields=["parent"],
		)
		for rc in row_counts:
			for v in chart_map.values():
				if v["name"] == rc.parent:
					v["points"] = v.get("points", 0) + 1

	charted = 0
	uncharted = 0
	result = []

	for t in tanks:
		c = chart_map.get(t.name)
		if c:
			charted += 1
			status = _("Charted")
		else:
			uncharted += 1
			status = _("No Chart")

		result.append(
			{
				"station": t.station,
				"tank": t.name,
				"item": t.item,
				"chart": c["name"] if c else "",
				"points": c["points"] if c else 0,
				"max_volume_l": c["max_volume_l"] if c else 0.0,
				"valid_from": c["valid_from"] if c else None,
				"source": c["source"] if c else "",
				"status": status,
			}
		)

	summary = [
		summary_card(charted, _("Charted"), datatype="Int", indicator="Green"),
		summary_card(
			uncharted,
			_("No Chart"),
			datatype="Int",
			indicator="Red" if uncharted else "Green",
		),
	]

	return result, summary
