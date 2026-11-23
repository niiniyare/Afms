"""Control Signals by Cashier — CTL-06.

Aggregates shortage, write-off and over-limit signals per cashier.
Sources: Cashier Ledger Entry (shortage / write-offs) and
Shift Credit Sale (over-limit events).

T-WTD: shortage_pct = total_shortage / fuel_amount * 100.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_shift_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "shortage_pct",
		"numerator": "total_shortage",
		"denominator": "fuel_amount",
		"multiplier": 100,
		"precision": 2,
	}
]


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
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Shifts"),
			"fieldname": "shifts",
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"label": _("Fuel Amount"),
			"fieldname": "fuel_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Total Shortage"),
			"fieldname": "total_shortage",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Shortage %"),
			"fieldname": "shortage_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Write-offs"),
			"fieldname": "write_offs",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Over-limit Events"),
			"fieldname": "over_limit_events",
			"fieldtype": "Int",
			"width": 120,
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

	cle_f: dict = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("company"):
		cle_f["company"] = filters["company"]
	if station_filter:
		cle_f["station"] = station_filter
	apply_date_filter(cle_f, filters, date_field="posting_date")

	cle_rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=cle_f,
		fields=["cashier", "station", "fuel_amount", "difference", "resolution_action"],
		order_by="cashier asc",
	)

	groups: dict[tuple, dict] = {}
	for row in cle_rows:
		key = (row.cashier or "", row.station or "")
		if key not in groups:
			groups[key] = {
				"shifts": 0,
				"fuel_amount": 0.0,
				"total_shortage": 0.0,
				"write_offs": 0,
			}
		groups[key]["shifts"] += 1
		groups[key]["fuel_amount"] += flt(row.fuel_amount)
		if flt(row.difference) < 0:
			groups[key]["total_shortage"] += abs(flt(row.difference))
		if (row.resolution_action or "").lower() in ("write off", "write-off"):
			groups[key]["write_offs"] += 1

	over_limit_map: dict[tuple, int] = {}
	if groups:
		shift_f: dict = {"docstatus": 1}
		if filters.get("company"):
			shift_f["company"] = filters["company"]
		if station_filter:
			shift_f["station"] = station_filter
		apply_shift_date_filter(shift_f, filters)

		shift_rows = frappe.get_all(
			"Forecourt Shift",
			filters=shift_f,
			fields=["name", "station"],
		)
		shift_names = [s.name for s in shift_rows]
		shift_station_map = {s.name: s.station for s in shift_rows}

		if shift_names:
			try:
				credit_sales = frappe.get_all(
					"Shift Credit Sale",
					filters={
						"parent": ["in", shift_names],
						"parenttype": "Forecourt Shift",
						"over_limit": 1,
					},
					fields=["cashier", "parent"],
				)
				for cs in credit_sales:
					station = shift_station_map.get(cs.parent, "")
					key = (cs.cashier or "", station)
					over_limit_map[key] = over_limit_map.get(key, 0) + 1
			except Exception:
				pass

	result: list[dict] = []
	for (cashier, station), g in sorted(groups.items(), key=lambda x: -x[1]["fuel_amount"]):
		key = (cashier, station)
		shortage_pct = flt(g["total_shortage"] / g["fuel_amount"] * 100, 2) if g["fuel_amount"] else 0.0
		result.append(
			{
				"cashier": cashier,
				"station": station,
				"shifts": g["shifts"],
				"fuel_amount": flt(g["fuel_amount"], 2),
				"total_shortage": flt(g["total_shortage"], 2),
				"shortage_pct": shortage_pct,
				"write_offs": g["write_offs"],
				"over_limit_events": over_limit_map.get(key, 0),
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_shortage = flt(sum(r["total_shortage"] for r in result), 2)
	summary = [
		summary_card(len(result), _("Cashiers"), datatype="Int"),
		summary_card(sum(r["shifts"] for r in result), _("Shifts"), datatype="Int"),
		summary_card(
			total_shortage,
			_("Total Shortage"),
			datatype="Currency",
			indicator="Orange" if total_shortage else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
