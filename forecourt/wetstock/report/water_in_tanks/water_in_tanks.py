"""Water in Tanks — WET-05.

One row per Tank Dip or Shift Tank Dip record that has water readings,
showing the change since the previous dip on the same tank.

Water data comes from the dip documents (gap G-01: not in Wetstock Ledger).

T-REG.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_reg,
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
		{"label": _("Date"), "fieldname": "dipped_at", "fieldtype": "Datetime", "width": 130},
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
			"width": 130,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Water (mm)"),
			"fieldname": "water_mm",
			"fieldtype": "Float",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Water (L)"),
			"fieldname": "water_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Change vs Previous (L)"),
			"fieldname": "change_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": _("Source"),
			"fieldname": "source_doctype",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Source Document"),
			"fieldname": "source_name",
			"fieldtype": "Dynamic Link",
			"options": "source_doctype",
			"width": 160,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	only_with_water = filters.get("only_with_water", 1)

	# --- Spot dips (Tank Dip) ---
	td_f: dict = {"docstatus": 1}
	if filters.get("company"):
		td_f["company"] = filters["company"]
	if filters.get("station"):
		td_f["station"] = filters["station"]
	if filters.get("tank"):
		td_f["tank"] = filters["tank"]
	apply_date_filter(td_f, filters, date_field="dipped_at")
	err = apply_station_permission(td_f, filters)
	if err:
		return [], []

	spot_dips = frappe.get_all(
		"Tank Dip",
		filters=td_f,
		fields=["name", "station", "tank", "item", "dipped_at", "water_mm", "water_l"],
		order_by="tank asc, dipped_at asc",
	)

	# --- Shift Tank Dips ---
	# Join via Forecourt Shift for station/date range
	shift_f: dict = {"docstatus": 1}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if filters.get("station"):
		shift_f["station"] = filters["station"]
	apply_date_filter(shift_f, filters, date_field="shift_date")

	shifts = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_date"],
	)
	if shifts:
		shift_names = [s.name for s in shifts]
		shift_map = {s.name: s for s in shifts}

		std_f: dict = {"parent": ["in", shift_names]}
		if filters.get("tank"):
			std_f["tank"] = filters["tank"]

		shift_tank_dips = frappe.get_all(
			"Shift Tank Dip",
			filters=std_f,
			fields=["parent", "tank", "item", "water_mm", "water_l"],
		)
	else:
		shift_tank_dips = []
		shift_map = {}

	# Collect all rows
	raw: list[dict] = []
	for sd in spot_dips:
		raw.append(
			{
				"tank": sd.tank,
				"station": sd.station,
				"item": sd.item,
				"dipped_at": sd.dipped_at,
				"water_mm": flt(sd.water_mm, 1),
				"water_l": flt(sd.water_l, 2),
				"source_doctype": "Tank Dip",
				"source_name": sd.name,
			}
		)
	for std in shift_tank_dips:
		s = shift_map.get(std.parent)
		if not s:
			continue
		raw.append(
			{
				"tank": std.tank,
				"station": s.station,
				"item": std.item,
				"dipped_at": str(s.shift_date),
				"water_mm": flt(std.water_mm, 1),
				"water_l": flt(std.water_l, 2),
				"source_doctype": "Forecourt Shift",
				"source_name": std.parent,
			}
		)

	# Sort by tank then dipped_at
	raw.sort(key=lambda x: (x["tank"] or "", str(x["dipped_at"] or "")))

	# Compute change vs previous dip per tank
	prev_water: dict[str, float] = {}
	result: list[dict] = []
	for row in raw:
		tank = row["tank"] or ""
		water_l = row["water_l"]
		prev = prev_water.get(tank)
		change_l = flt(water_l - prev, 2) if prev is not None else None
		prev_water[tank] = water_l
		row["change_l"] = change_l

		if only_with_water and not water_l:
			continue
		result.append(row)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="dipped_at") if result else {}

	tanks_with_water = len({r["tank"] for r in result if r["water_l"]})
	summary = [
		summary_card(len(result), _("Dip Records"), datatype="Int"),
		summary_card(
			tanks_with_water,
			_("Tanks with Water"),
			datatype="Int",
			indicator="Orange" if tanks_with_water else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
