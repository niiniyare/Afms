"""Price History — PRC-01.

One row per Fuel Price Change Item on submitted (Approved) Fuel Price
Changes: when the price changed, old and new price, who approved it.

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
			"label": _("Effective At"),
			"fieldname": "effective_at",
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
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Old Price"),
			"fieldname": "old_price",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": _("New Price"),
			"fieldname": "new_price",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": _("Change"),
			"fieldname": "change",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": _("Change %"),
			"fieldname": "change_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 90,
		},
		{"label": _("Reason"), "fieldname": "reason", "fieldtype": "Data", "width": 180},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 120},
		{
			"label": _("Price Change"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Fuel Price Change",
			"width": 160,
		},
		{
			"label": _("Applied to Shift"),
			"fieldname": "applied_to_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
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
		fields=["name", "station", "effective_at", "reason", "reference", "applied_to_shift"],
		order_by="effective_at asc",
	)
	if not fpcs:
		return [], []

	fpc_names = [fpc.name for fpc in fpcs]
	fpc_map = {fpc.name: fpc for fpc in fpcs}

	item_f: dict = {"parent": ["in", fpc_names]}
	if filters.get("item"):
		item_f["item"] = filters["item"]

	items = frappe.get_all(
		"Fuel Price Change Item",
		filters=item_f,
		fields=["parent", "item", "old_price", "new_price"],
		order_by="parent asc",
	)

	result: list[dict] = []
	for it in items:
		fpc = fpc_map[it.parent]
		old_p = flt(it.old_price, 4)
		new_p = flt(it.new_price, 4)
		change = flt(new_p - old_p, 4)
		change_pct = flt((change / old_p * 100) if old_p else 0, 2)
		result.append(
			{
				"effective_at": fpc.effective_at,
				"station": fpc.station,
				"item": it.item,
				"old_price": old_p,
				"new_price": new_p,
				"change": change,
				"change_pct": change_pct,
				"reason": fpc.reason or "",
				"reference": fpc.reference or "",
				"name": fpc.name,
				"applied_to_shift": fpc.applied_to_shift,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="effective_at") if result else {}

	summary = [
		summary_card(len(result), _("Price Changes"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
