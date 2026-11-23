"""Receipts Awaiting Invoice — PUR-02.

Submitted Purchase Receipts that have no matching Purchase Invoice.
Identifies fuel GRNs where billing is overdue.

T-REG: count rows.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

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
			"label": _("GRN"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
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
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
		},
		{
			"label": _("Delivery Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Days Open"),
			"fieldname": "days_open",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Invoiced L"),
			"fieldname": "invoiced_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Value"),
			"fieldname": "value",
			"fieldtype": "Currency",
			"width": 110,
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

	pr_f: dict = {"docstatus": 1, "per_billed": ["<", 100]}
	if filters.get("company"):
		pr_f["company"] = filters["company"]
	if station_filter:
		pr_f["station"] = station_filter
	if filters.get("supplier"):
		pr_f["supplier"] = filters["supplier"]
	apply_date_filter(pr_f, filters)

	pr_rows = frappe.get_all(
		"Purchase Receipt",
		filters=pr_f,
		fields=["name", "station", "supplier", "posting_date", "net_total"],
		order_by="posting_date asc",
	)
	if not pr_rows:
		return [], []

	pr_names = [pr.name for pr in pr_rows]
	# Fuel item quantities
	item_rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": ["in", pr_names]},
		fields=["parent", "qty"],
	)
	inv_map: dict[str, float] = {}
	for it in item_rows:
		inv_map[it.parent] = flt(inv_map.get(it.parent, 0) + flt(it.qty, 2), 2)

	today = getdate(nowdate())
	result: list[dict] = []
	for pr in pr_rows:
		posting = getdate(pr.posting_date)
		days_open = (today - posting).days
		result.append(
			{
				"name": pr.name,
				"station": pr.station,
				"supplier": pr.supplier,
				"posting_date": pr.posting_date,
				"days_open": days_open,
				"invoiced_l": inv_map.get(pr.name, 0),
				"value": flt(pr.net_total, 2),
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	total_value = sum(r["value"] for r in result)
	summary = [
		summary_card(len(result), _("GRNs Awaiting Invoice"), datatype="Int"),
		summary_card(total_value, _("Value"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
