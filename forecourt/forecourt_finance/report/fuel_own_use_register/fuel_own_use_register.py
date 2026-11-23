"""Fuel Own Use Register — EXP-03.

One row per submitted Fuel Own Use Stock Entry item, showing purpose,
quantity, valuation and the shift it was posted for.

Stock Entries of type "Fuel Own Use" have:
  - `fms_forecourt_shift`: Link Forecourt Shift
  - `fms_use_purpose`: Link Own Use Purpose
  - `fms_attendant`: Link Employee
  - `station`: accounting dimension field

T-ADD: qty_l, amount summed.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_add,
	validate_date_range,
)

_OWN_USE_TYPE = "Fuel Own Use"


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
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Stock Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Stock Entry",
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
			"label": _("Purpose"),
			"fieldname": "purpose",
			"fieldtype": "Link",
			"options": "Own Use Purpose",
			"width": 140,
		},
		{
			"label": _("Attendant"),
			"fieldname": "attendant",
			"fieldtype": "Link",
			"options": "Employee",
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
			"label": _("Qty (L)"),
			"fieldname": "qty_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Valuation Rate"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{
			"label": _("Narration"),
			"fieldname": "narration",
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

	se_f: dict = {"docstatus": 1, "stock_entry_type": _OWN_USE_TYPE}
	if filters.get("company"):
		se_f["company"] = filters["company"]
	if station_filter:
		se_f["station"] = station_filter
	if filters.get("purpose"):
		se_f["fms_use_purpose"] = filters["purpose"]
	apply_date_filter(se_f, filters)

	se_rows = frappe.get_all(
		"Stock Entry",
		filters=se_f,
		fields=[
			"name",
			"posting_date",
			"station",
			"fms_use_purpose",
			"fms_attendant",
			"fms_forecourt_shift",
			"remarks",
		],
		order_by="posting_date asc",
	)
	if not se_rows:
		return [], []

	se_names = [se.name for se in se_rows]
	se_map = {se.name: se for se in se_rows}

	item_f: dict = {"parent": ["in", se_names]}
	if filters.get("item"):
		item_f["item_code"] = filters["item"]

	items = frappe.get_all(
		"Stock Entry Detail",
		filters=item_f,
		fields=["parent", "item_code", "qty", "valuation_rate", "amount"],
	)

	result: list[dict] = []
	for it in items:
		se = se_map.get(it.parent)
		if not se:
			continue
		qty = flt(it.qty, 2)
		rate = flt(it.valuation_rate, 4)
		amount = flt(it.amount, 2)
		result.append(
			{
				"posting_date": se.posting_date,
				"name": se.name,
				"station": se.station,
				"purpose": se.fms_use_purpose,
				"attendant": se.fms_attendant,
				"item": it.item_code,
				"qty_l": qty,
				"valuation_rate": rate,
				"amount": amount,
				"shift": se.fms_forecourt_shift,
				"narration": se.remarks or "",
			}
		)

	result.sort(key=lambda r: (str(r["posting_date"]), str(r["name"])))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_qty = sum(r["qty_l"] for r in result)
	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("Own Use Entries"), datatype="Int"),
		summary_card(total_qty, _("Total Litres"), datatype="Float"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
