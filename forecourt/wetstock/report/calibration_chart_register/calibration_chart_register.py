"""Calibration Chart Register — EQP-03.

Master list of Tank Calibration Charts per station.
Shows tank, product, row count and whether a water chart exists.
No date filter — snapshot of current charts.

T-REG: count rows.
"""

from __future__ import annotations

import frappe
from frappe import _

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
			"label": _("Chart"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Tank Calibration Chart",
			"width": 160,
		},
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
			"label": _("Fuel Rows"),
			"fieldname": "fuel_rows",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Water Rows"),
			"fieldname": "water_rows",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Has Water Chart"),
			"fieldname": "has_water",
			"fieldtype": "Check",
			"width": 110,
		},
		{
			"label": _("Max Depth (mm)"),
			"fieldname": "max_depth_mm",
			"fieldtype": "Float",
			"precision": 0,
			"width": 110,
		},
		{
			"label": _("Max Volume (L)"),
			"fieldname": "max_volume_l",
			"fieldtype": "Float",
			"precision": 0,
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

	chart_f: dict = {}
	if station_filter:
		chart_f["station"] = station_filter
	if filters.get("item"):
		chart_f["item"] = filters["item"]

	charts = frappe.get_all(
		"Tank Calibration Chart",
		filters=chart_f,
		fields=["name", "station", "tank", "item"],
		order_by="station asc, tank asc",
	)
	if not charts:
		return [], []

	chart_names = [c.name for c in charts]

	# Count fuel rows and water rows per chart
	fuel_rows = frappe.get_all(
		"Tank Calibration Row",
		filters={"parent": ["in", chart_names], "parentfield": "rows"},
		fields=["parent", "depth_mm", "volume_l"],
	)
	water_rows = frappe.get_all(
		"Tank Calibration Row",
		filters={"parent": ["in", chart_names], "parentfield": "water_rows"},
		fields=["parent", "depth_mm", "volume_l"],
	)

	fuel_count: dict[str, int] = {}
	for r in fuel_rows:
		fuel_count[r.parent] = fuel_count.get(r.parent, 0) + 1

	water_count: dict[str, int] = {}
	for r in water_rows:
		water_count[r.parent] = water_count.get(r.parent, 0) + 1

	# Max depth and volume from fuel rows
	max_depth: dict[str, float] = {}
	max_vol: dict[str, float] = {}
	for r in fuel_rows:
		if r.depth_mm and r.depth_mm > max_depth.get(r.parent, 0):
			max_depth[r.parent] = r.depth_mm
		if r.volume_l and r.volume_l > max_vol.get(r.parent, 0):
			max_vol[r.parent] = r.volume_l

	result: list[dict] = []
	for c in charts:
		wc = water_count.get(c.name, 0)
		result.append(
			{
				"name": c.name,
				"station": c.station,
				"tank": c.tank,
				"item": c.item,
				"fuel_rows": fuel_count.get(c.name, 0),
				"water_rows": wc,
				"has_water": 1 if wc > 0 else 0,
				"max_depth_mm": max_depth.get(c.name, 0),
				"max_volume_l": max_vol.get(c.name, 0),
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	with_water = sum(1 for r in result if r["has_water"])
	summary = [
		summary_card(len(result), _("Calibration Charts"), datatype="Int"),
		summary_card(with_water, _("With Water Chart"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
