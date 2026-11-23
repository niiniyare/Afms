"""Pump Test Register — MTR-05.

Per-nozzle (or cashier/station) summary of test volumes:
how much fuel was drawn through the pump to verify calibration,
who did it, and whether shifts exceeded the nozzle limit.

Excessive test volumes are a known method for hiding sales (fms.md 7.4).

T-WTD: test_pct recomputed from summed test_l and net_l.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "test_pct",
		"numerator": "test_l",
		"denominator": "net_l",
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
			"label": _("Nozzle"),
			"fieldname": "nozzle",
			"fieldtype": "Link",
			"options": "Nozzle",
			"width": 130,
		},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Shifts"), "fieldname": "shifts", "fieldtype": "Int", "width": 60},
		{
			"label": _("Test Litres"),
			"fieldname": "test_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Litres Sold"),
			"fieldname": "net_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Test % of Sales"),
			"fieldname": "test_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Nozzle Limit (L/shift)"),
			"fieldname": "nozzle_limit",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{
			"label": _("Shifts Above Limit"),
			"fieldname": "shifts_above_limit",
			"fieldtype": "Int",
			"width": 120,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"test_l": [">", 0],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("nozzle"):
		f["nozzle"] = filters["nozzle"]
	if filters.get("cashier"):
		f["cashier"] = filters["cashier"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	entries = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=f,
		fields=["nozzle", "cashier", "station", "test_l", "net_l"],
	)

	# Fetch nozzle test limits (if stored on Nozzle doctype)
	nozzle_limits: dict[str, float] = {}
	nozzles = list({e.nozzle for e in entries if e.nozzle})
	if nozzles:
		nozzle_docs = frappe.get_all(
			"Nozzle",
			filters={"name": ["in", nozzles]},
			fields=["name", "test_volume_limit_l"],
		)
		for nd in nozzle_docs:
			if nd.get("test_volume_limit_l"):
				nozzle_limits[nd.name] = flt(nd.test_volume_limit_l, 2)

	# Group by nozzle + cashier + station
	key_map: dict[tuple, dict] = {}
	for e in entries:
		key = (e.nozzle or "", e.cashier or "", e.station or "")
		if key not in key_map:
			key_map[key] = {
				"nozzle": e.nozzle,
				"cashier": e.cashier,
				"station": e.station,
				"shifts": 0,
				"test_l": 0.0,
				"net_l": 0.0,
				"shifts_above_limit": 0,
			}
		km = key_map[key]
		km["shifts"] += 1
		km["test_l"] = flt(km["test_l"] + flt(e.test_l, 2), 2)
		km["net_l"] = flt(km["net_l"] + flt(e.net_l, 2), 2)

		# Count per-shift above-limit occurrences
		limit = nozzle_limits.get(e.nozzle or "", 0)
		if limit and flt(e.test_l, 2) > limit:
			km["shifts_above_limit"] += 1

	only_above = filters.get("only_above_limit")
	result: list[dict] = []
	for km in sorted(key_map.values(), key=lambda x: (x["nozzle"] or "", x["cashier"] or "")):
		net_l = flt(km["net_l"], 2)
		test_l = flt(km["test_l"], 2)
		test_pct = flt((test_l / net_l * 100) if net_l else 0, 2)
		nozzle_limit = nozzle_limits.get(km["nozzle"] or "", 0)

		if only_above and not km["shifts_above_limit"]:
			continue

		result.append(
			{
				"nozzle": km["nozzle"],
				"cashier": km["cashier"],
				"station": km["station"],
				"shifts": km["shifts"],
				"test_l": test_l,
				"net_l": net_l,
				"test_pct": test_pct,
				"nozzle_limit": nozzle_limit,
				"shifts_above_limit": km["shifts_above_limit"],
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_test_l = sum(r["test_l"] for r in result)
	nozzles_above = sum(1 for r in result if r["shifts_above_limit"] > 0)
	summary = [
		summary_card(len(result), _("Nozzle/Cashier Pairs"), datatype="Int"),
		summary_card(total_test_l, _("Total Test Litres"), datatype="Float"),
		summary_card(
			nozzles_above,
			_("Nozzles with Limit Exceedances"),
			datatype="Int",
			indicator="Orange" if nozzles_above else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
