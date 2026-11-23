"""Meter Continuity Exceptions — MTR-04.

One row per break in the nozzle reading chain within the requested period:
  gap (opening ≠ previous closing), rollover, meter change, manual
  adjustment, or correction.

A gap with no Meter Change or Shift Correction to explain it is flagged as
Unexplained (shown in red on the client).

T-REG: count by type.
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

_TYPES_ALL = ("Gap", "Rollover", "Meter Change", "Manual Adjustment", "Correction")


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
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
			"width": 120,
		},
		{
			"label": _("Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Previous Closing"),
			"fieldname": "prev_closing",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("This Opening"),
			"fieldname": "this_opening",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Difference"),
			"fieldname": "difference",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{"label": _("Type"), "fieldname": "exception_type", "fieldtype": "Data", "width": 110},
		{
			"label": _("Explained By"),
			"fieldname": "explained_by",
			"fieldtype": "Data",
			"width": 160,
		},
		{"label": _("Flag"), "fieldname": "flag", "fieldtype": "Data", "width": 100},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	entries = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=f,
		fields=[
			"name",
			"posting_date",
			"station",
			"nozzle",
			"forecourt_shift",
			"opening_ecash",
			"closing_ecash",
			"source",
		],
		order_by="nozzle asc, posting_date asc, name asc",
	)

	requested_type = filters.get("exception_type")

	# Build per-nozzle ordered list to detect breaks
	nozzle_entries: dict[str, list] = {}
	for e in entries:
		nozzle_entries.setdefault(e.nozzle or "", []).append(e)

	# Also fetch Meter Change records in range for explanation lookup
	mc_f: dict = {"docstatus": 1}
	if filters.get("station"):
		mc_f["station"] = filters["station"]
	apply_date_filter(mc_f, filters, date_field="changed_at")
	meter_changes = frappe.get_all(
		"Meter Change",
		filters=mc_f,
		fields=["name", "nozzle", "changed_at"],
	)
	mc_by_nozzle: dict[str, list[str]] = {}
	for mc in meter_changes:
		mc_by_nozzle.setdefault(mc.nozzle or "", []).append(mc.name)

	rows: list[dict] = []
	type_counts: dict[str, int] = {}

	for nozzle, nle_list in nozzle_entries.items():
		for i, entry in enumerate(nle_list):
			if i == 0:
				continue  # no previous entry in this window
			prev = nle_list[i - 1]
			prev_closing = flt(prev.closing_ecash, 2)
			this_opening = flt(entry.opening_ecash, 2)
			diff = flt(this_opening - prev_closing, 2)

			if diff == 0:
				continue  # chain is continuous

			# Classify
			if diff < 0:
				exc_type = "Rollover"
			elif entry.source == "Meter Change":
				exc_type = "Meter Change"
			elif entry.source == "Adjustment":
				exc_type = "Manual Adjustment"
			elif entry.source == "Correction":
				exc_type = "Correction"
			else:
				exc_type = "Gap"

			if requested_type and exc_type != requested_type:
				continue

			# Build explanation reference
			explained_by = ""
			if exc_type == "Meter Change":
				mcs = mc_by_nozzle.get(nozzle, [])
				explained_by = mcs[0] if mcs else ""
			elif exc_type == "Correction":
				explained_by = entry.source or ""
			elif exc_type == "Rollover":
				explained_by = _("Meter rollover")

			flag = "Unexplained" if exc_type == "Gap" and not explained_by else "Explained"

			type_counts[exc_type] = type_counts.get(exc_type, 0) + 1
			rows.append(
				{
					"posting_date": entry.posting_date,
					"station": entry.station,
					"nozzle": nozzle,
					"forecourt_shift": entry.forecourt_shift,
					"prev_closing": prev_closing,
					"this_opening": this_opening,
					"difference": diff,
					"exception_type": exc_type,
					"explained_by": explained_by,
					"flag": flag,
				}
			)

	cols = _columns()
	total = total_row_reg(rows, cols, count_label="posting_date") if rows else {}

	unexplained = sum(1 for r in rows if r["flag"] == "Unexplained")
	summary = [
		summary_card(len(rows), _("Exceptions"), datatype="Int"),
		summary_card(
			unexplained,
			_("Unexplained Gaps"),
			datatype="Int",
			indicator="Red" if unexplained else "Green",
		),
		summary_card(type_counts.get("Gap", 0), _("Gaps"), datatype="Int"),
		summary_card(type_counts.get("Meter Change", 0), _("Meter Changes"), datatype="Int"),
	]

	if total:
		rows.append(total)

	return rows, summary
