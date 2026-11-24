"""Single authoritative source for shift opening balances (meters and tanks).

Both nozzle meter openings and tank opening litres come from the same place:
the closing readings of the latest SUBMITTED shift at the station. Draft and
cancelled shifts are never used. Where a nozzle or tank is absent from that
shift, the configured initial value on the master is used.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.errors import FMS_S116

_METER_KEYS = ("opening_elec_cash", "opening_elec_meter", "opening_man_meter")


def latest_submitted_shift(station: str) -> str | None:
	rows = frappe.get_all(
		"Forecourt Shift",
		filters={"station": station, "docstatus": 1},
		fields=["name"],
		order_by="shift_start desc",
		limit=1,
	)
	return rows[0].name if rows else None


def open_drafts(station: str, exclude: str | None = None) -> list[str]:
	"""Names of every unabandoned draft shift at *station* (oldest first)."""
	filters: list = [
		["station", "=", station],
		["docstatus", "=", 0],
		["status", "!=", "Abandoned"],
	]
	if exclude:
		filters.append(["name", "!=", exclude])
	return [
		r.name
		for r in frappe.get_all("Forecourt Shift", filters=filters, fields=["name"], order_by="creation asc")
	]


def draft_conflict_message(station: str, drafts: list[str]) -> str:
	return _(
		"[{0}] Open draft shift(s) at {1}: {2}. Submit the one in use, or abandon the others "
		"(Forecourt Shift > Abandon Draft) before opening another shift."
	).format(FMS_S116, station, ", ".join(drafts))


def nozzle_openings(nozzle: str, previous_shift: str | None) -> dict[str, float]:
	"""Opening meter values for *nozzle*, keyed by Shift Meter Reading field names."""
	prev_end = None
	if previous_shift:
		prev_end = frappe.db.get_value("Forecourt Shift", previous_shift, "shift_end")
		rows = frappe.get_all(
			"Shift Meter Reading",
			filters={"parent": previous_shift, "parenttype": "Forecourt Shift", "nozzle": nozzle},
			fields=["segment_no", "closing_elec_cash", "closing_elec_meter", "closing_man_meter"],
			order_by="segment_no desc, idx desc",
			limit=1,
		)
		from_shift = (
			{
				"opening_elec_cash": flt(rows[0].closing_elec_cash),
				"opening_elec_meter": flt(rows[0].closing_elec_meter),
				"opening_man_meter": flt(rows[0].closing_man_meter),
			}
			if rows
			else None
		)
	else:
		from_shift = None

	change_filters: dict = {"nozzle": nozzle, "docstatus": 1}
	if prev_end:
		change_filters["changed_at"] = [">", prev_end]
	change = frappe.get_all(
		"Meter Change",
		filters=change_filters,
		fields=["new_start_ecash", "new_start_evol", "new_start_mvol"],
		order_by="changed_at desc",
		limit=1,
	)
	if change:
		return {
			"opening_elec_cash": flt(change[0].new_start_ecash),
			"opening_elec_meter": flt(change[0].new_start_evol),
			"opening_man_meter": flt(change[0].new_start_mvol),
		}
	if from_shift is not None:
		return from_shift

	cfg = frappe.db.get_value(
		"Nozzle",
		nozzle,
		[
			"opening_date",
			"opening_ecash",
			"opening_evol",
			"opening_mvol",
			"last_ecash",
			"last_evol",
			"last_mvol",
		],
		as_dict=True,
	)
	if not cfg:
		return dict.fromkeys(_METER_KEYS, 0.0)
	if cfg.opening_date or cfg.opening_ecash or cfg.opening_evol or cfg.opening_mvol:
		return {
			"opening_elec_cash": flt(cfg.opening_ecash),
			"opening_elec_meter": flt(cfg.opening_evol),
			"opening_man_meter": flt(cfg.opening_mvol),
		}
	return {
		"opening_elec_cash": flt(cfg.last_ecash),
		"opening_elec_meter": flt(cfg.last_evol),
		"opening_man_meter": flt(cfg.last_mvol),
	}


def tank_opening(tank: str, previous_shift: str | None) -> float:
	"""Opening litres for *tank*: previous submitted shift closing dip, else configured opening."""
	if previous_shift:
		rows = frappe.get_all(
			"Shift Tank Dip",
			filters={"parent": previous_shift, "parenttype": "Forecourt Shift", "tank": tank},
			fields=["dip_l"],
			limit=1,
		)
		if rows:
			return flt(rows[0].dip_l)
	return flt(frappe.db.get_value("Fuel Tank", tank, "opening_dip_l"))
