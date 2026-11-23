"""Spot Dip Register — WET-06.

Every submitted spot dip (Tank Dip), showing dip readings against the
book stock from the most recent Wetstock Ledger Entry.

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
		{
			"label": _("Dipped At"),
			"fieldname": "dipped_at",
			"fieldtype": "Datetime",
			"width": 130,
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
			"width": 130,
		},
		{
			"label": _("Purpose"),
			"fieldname": "purpose",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Dip (mm)"),
			"fieldname": "dip_mm",
			"fieldtype": "Float",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Volume (L)"),
			"fieldname": "volume_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Book (L)"),
			"fieldname": "book_volume_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Difference (L)"),
			"fieldname": "difference_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Difference %"),
			"fieldname": "difference_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Dipped By"),
			"fieldname": "dipped_by",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": _("Witness"),
			"fieldname": "witness",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"docstatus": 1}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]
	if filters.get("purpose"):
		f["purpose"] = filters["purpose"]
	if filters.get("dipped_by"):
		f["dipped_by"] = filters["dipped_by"]
	apply_date_filter(f, filters, date_field="dipped_at")
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	dips = frappe.get_all(
		"Tank Dip",
		filters=f,
		fields=[
			"name",
			"station",
			"tank",
			"purpose",
			"dipped_at",
			"dip_mm",
			"water_mm",
			"volume_l",
			"water_l",
			"book_volume_l",
			"difference_l",
			"dipped_by",
			"witness",
		],
		order_by="dipped_at asc",
	)

	requested_dipped_by = filters.get("dipped_by")
	result: list[dict] = []
	for d in dips:
		if requested_dipped_by and d.dipped_by != requested_dipped_by:
			continue
		book_l = flt(d.book_volume_l, 2)
		vol_l = flt(d.volume_l, 2)
		diff_l = flt(d.difference_l, 2) if d.difference_l is not None else flt(vol_l - book_l, 2)
		diff_pct = flt((diff_l / book_l * 100) if book_l else 0, 2)
		result.append(
			{
				"dipped_at": d.dipped_at,
				"station": d.station,
				"tank": d.tank,
				"purpose": d.purpose,
				"dip_mm": flt(d.dip_mm, 1),
				"volume_l": vol_l,
				"book_volume_l": book_l,
				"difference_l": diff_l,
				"difference_pct": diff_pct,
				"dipped_by": d.dipped_by,
				"witness": d.witness,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="dipped_at") if result else {}

	summary = [
		summary_card(len(result), _("Dips"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
