"""Equipment Health — EQP-04.

Health summary per station: active vs out-of-service nozzle counts,
tanks with no recent dip, nozzles with no shift in the last 7 days,
and nozzles out of service. Flags stations needing attention.

No date filter — snapshot of current equipment status plus recency checks.
T-REG: count rows.
"""

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_reg,
)

_IDLE_DAYS = 7
_DIP_STALE_DAYS = 3


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
			"width": 140,
		},
		{
			"label": _("Active Nozzles"),
			"fieldname": "active_nozzles",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Out of Service"),
			"fieldname": "oos_nozzles",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Idle Nozzles (7d)"),
			"fieldname": "idle_nozzles",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Stale Dips (3d)"),
			"fieldname": "stale_dips",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("No Calibration"),
			"fieldname": "uncalibrated_tanks",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Flag"),
			"fieldname": "flag",
			"fieldtype": "Data",
			"width": 160,
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

	nozzles = frappe.get_all(
		"Nozzle",
		filters=nozzle_f,
		fields=["name", "station", "tank", "status", "last_reading_shift"],
	)
	if not nozzles:
		return [], []

	today = getdate(nowdate())
	idle_cutoff = today - timedelta(days=_IDLE_DAYS)
	dip_cutoff = today - timedelta(days=_DIP_STALE_DAYS)

	# Last shift date per nozzle from NLE
	nozzle_names = [n.name for n in nozzles]
	nle_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters={
			"is_cancelled": 0,
			"nozzle": ["in", nozzle_names],
			"posting_date": [">=", str(idle_cutoff)],
		},
		fields=["nozzle"],
		distinct=True,
	)
	recently_active = {r.nozzle for r in nle_rows}

	# Last dip per tank
	all_tanks = list({n.tank for n in nozzles if n.tank})
	stale_tanks: set[str] = set()
	if all_tanks:
		dip_rows = frappe.get_all(
			"Wetstock Ledger Entry",
			filters={
				"is_cancelled": 0,
				"entry_type": "Shift",
				"tank": ["in", all_tanks],
				"posting_date": [">=", str(dip_cutoff)],
			},
			fields=["tank"],
			distinct=True,
		)
		recently_dipped = {r.tank for r in dip_rows}
		stale_tanks = set(all_tanks) - recently_dipped

	# Tanks with calibration charts
	calibrated_tanks: set[str] = set()
	if all_tanks:
		charts = frappe.get_all(
			"Tank Calibration Chart",
			filters={"tank": ["in", all_tanks]},
			fields=["tank"],
		)
		calibrated_tanks = {c.tank for c in charts}

	# Group by station
	stations: dict[str, dict] = {}
	for n in nozzles:
		st = n.station or ""
		if st not in stations:
			stations[st] = {
				"station": st,
				"active_nozzles": 0,
				"oos_nozzles": 0,
				"idle_nozzles": 0,
				"stale_dips": 0,
				"uncalibrated_tanks": 0,
				"_tanks": set(),
			}
		s = stations[st]
		if n.status == "Active":
			s["active_nozzles"] += 1
		else:
			s["oos_nozzles"] += 1
		if n.name not in recently_active and n.status == "Active":
			s["idle_nozzles"] += 1
		if n.tank:
			if n.tank not in s["_tanks"]:
				s["_tanks"].add(n.tank)
				if n.tank in stale_tanks:
					s["stale_dips"] += 1
				if n.tank not in calibrated_tanks:
					s["uncalibrated_tanks"] += 1

	result: list[dict] = []
	for s in sorted(stations.values(), key=lambda x: x["station"]):
		flags = []
		if s["oos_nozzles"] > 0:
			flags.append(_("{0} nozzle(s) OOS").format(s["oos_nozzles"]))
		if s["idle_nozzles"] > 0:
			flags.append(_("{0} idle").format(s["idle_nozzles"]))
		if s["stale_dips"] > 0:
			flags.append(_("{0} stale dip(s)").format(s["stale_dips"]))
		if s["uncalibrated_tanks"] > 0:
			flags.append(_("{0} no chart").format(s["uncalibrated_tanks"]))
		result.append(
			{
				"station": s["station"],
				"active_nozzles": s["active_nozzles"],
				"oos_nozzles": s["oos_nozzles"],
				"idle_nozzles": s["idle_nozzles"],
				"stale_dips": s["stale_dips"],
				"uncalibrated_tanks": s["uncalibrated_tanks"],
				"flag": "; ".join(flags),
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="station") if result else {}

	flagged = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(len(result), _("Stations"), datatype="Int"),
		summary_card(
			flagged,
			_("Need Attention"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
