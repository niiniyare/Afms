"""Price Change Compliance — PRC-02.

One row per submitted Fuel Price Change: delay from effective to approval,
whether a segment was created, and cross-check failures from NLE amounts
vs volume * price (fms.md 5.6).

T-REG: count by flag.
"""

from __future__ import annotations

from datetime import datetime

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

_TOLERANCE = 1.0  # currency units; fms.md 5.6 price cross-check


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
			"label": _("Price Change"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Fuel Price Change",
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
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Effective At"),
			"fieldname": "effective_at",
			"fieldtype": "Datetime",
			"width": 130,
		},
		{
			"label": _("Delay (hrs)"),
			"fieldname": "delay_hours",
			"fieldtype": "Float",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Segment Created"),
			"fieldname": "segment_created",
			"fieldtype": "Check",
			"width": 110,
		},
		{
			"label": _("Cross-check Failures"),
			"fieldname": "xcheck_failures",
			"fieldtype": "Int",
			"width": 140,
		},
		{"label": _("Flag"), "fieldname": "flag", "fieldtype": "Data", "width": 120},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"docstatus": 1}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	apply_date_filter(f, filters, date_field="effective_at")
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	fpcs = frappe.get_all(
		"Fuel Price Change",
		filters=f,
		fields=["name", "station", "effective_at", "modified", "applied_to_shift"],
		order_by="effective_at asc",
	)
	if not fpcs:
		return [], []

	fpc_names = [fpc.name for fpc in fpcs]

	# Items for product breakdown
	items = frappe.get_all(
		"Fuel Price Change Item",
		filters={"parent": ["in", fpc_names]},
		fields=["parent", "item", "new_price"],
	)
	fpc_items: dict[str, list] = {}
	for it in items:
		fpc_items.setdefault(it.parent, []).append(it)

	# NLE cross-check per fpc: get NLE rows in segments linked to this price change
	# Simplified: check NLE rows for shifts that used this price change via applied_to_shift
	shift_names = [fpc.applied_to_shift for fpc in fpcs if fpc.applied_to_shift]
	xcheck_map: dict[str, int] = {}
	if shift_names:
		nle_rows = frappe.get_all(
			"Nozzle Ledger Entry",
			filters={
				"is_cancelled": 0,
				"superseded_by": ["is", "not set"],
				"forecourt_shift": ["in", shift_names],
			},
			fields=["forecourt_shift", "amount", "net_l", "price"],
		)
		# Map shift to fpc name
		shift_to_fpc = {fpc.applied_to_shift: fpc.name for fpc in fpcs if fpc.applied_to_shift}
		for nle in nle_rows:
			expected = flt(flt(nle.net_l, 2) * flt(nle.price, 4), 2)
			actual = flt(nle.amount, 2)
			if abs(actual - expected) > _TOLERANCE:
				fpc_name = shift_to_fpc.get(nle.forecourt_shift or "")
				if fpc_name:
					xcheck_map[fpc_name] = xcheck_map.get(fpc_name, 0) + 1

	only_exceptions = filters.get("only_exceptions")

	result: list[dict] = []
	for fpc in fpcs:
		effective = fpc.effective_at
		submitted_at = fpc.modified  # proxy for approval time
		delay_hours = None
		if effective and submitted_at:
			eff_dt = effective if isinstance(effective, datetime) else datetime.fromisoformat(str(effective))
			sub_dt = (
				submitted_at
				if isinstance(submitted_at, datetime)
				else datetime.fromisoformat(str(submitted_at))
			)
			delay_hours = flt((sub_dt - eff_dt).total_seconds() / 3600, 1)

		segment_created = 1 if fpc.applied_to_shift else 0
		xcheck = xcheck_map.get(fpc.name, 0)

		flags: list[str] = []
		if delay_hours is not None and delay_hours > 24:
			flags.append(_("Late approval"))
		if not segment_created:
			flags.append(_("No segment"))
		if xcheck > 0:
			flags.append(_("{0} cross-check fail(s)").format(xcheck))
		flag = "; ".join(flags)

		if only_exceptions and not flag:
			continue

		# Items list for product column (comma-sep)
		item_list = ", ".join(it.item for it in fpc_items.get(fpc.name, []))

		result.append(
			{
				"name": fpc.name,
				"station": fpc.station,
				"item": item_list,
				"effective_at": effective,
				"delay_hours": delay_hours,
				"segment_created": segment_created,
				"xcheck_failures": xcheck,
				"flag": flag,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	flagged = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(len(result), _("Price Changes"), datatype="Int"),
		summary_card(
			flagged,
			_("Exceptions"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
