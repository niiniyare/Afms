"""Delivery Delay — DLV-04.

Time from delivery posting_date to GRN submission (modified when docstatus=1).
One row per Purchase Receipt. Flags deliveries posted more than N days after receipt.

T-REG: count by flag.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt, getdate

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_reg,
	validate_date_range,
)

_LATE_DAYS = 2  # Flag GRNs submitted more than 2 days after delivery


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
			"label": _("Submitted At"),
			"fieldname": "submitted_at",
			"fieldtype": "Datetime",
			"width": 130,
		},
		{
			"label": _("Delay (days)"),
			"fieldname": "delay_days",
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{
			"label": _("Invoiced L"),
			"fieldname": "invoiced_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Flag"),
			"fieldname": "flag",
			"fieldtype": "Data",
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

	pr_f: dict = {"docstatus": 1}
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
		fields=["name", "station", "supplier", "posting_date", "modified"],
		order_by="posting_date asc",
	)
	if not pr_rows:
		return [], []

	# Invoiced litres from items (fuel only via is_fuel_item or just qty)
	pr_names = [pr.name for pr in pr_rows]
	item_rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": ["in", pr_names]},
		fields=["parent", "qty"],
	)
	inv_map: dict[str, float] = {}
	for it in item_rows:
		inv_map[it.parent] = flt(inv_map.get(it.parent, 0) + flt(it.qty, 2), 2)

	only_late = filters.get("only_late")

	result: list[dict] = []
	for pr in pr_rows:
		posting = getdate(pr.posting_date)
		submitted_at = pr.modified
		delay_days = None
		if submitted_at:
			sub_dt = (
				submitted_at
				if isinstance(submitted_at, datetime)
				else datetime.fromisoformat(str(submitted_at))
			)
			posting_dt = datetime(posting.year, posting.month, posting.day)
			delay_days = flt((sub_dt - posting_dt).total_seconds() / 86400, 1)

		late = delay_days is not None and delay_days > _LATE_DAYS
		flag = _("Late ({0}d)").format(delay_days) if late else ""

		if only_late and not flag:
			continue

		result.append(
			{
				"name": pr.name,
				"station": pr.station,
				"supplier": pr.supplier,
				"posting_date": pr.posting_date,
				"submitted_at": submitted_at,
				"delay_days": delay_days,
				"invoiced_l": inv_map.get(pr.name, 0),
				"flag": flag,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	flagged = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(len(result), _("GRNs"), datatype="Int"),
		summary_card(
			flagged,
			_("Late"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
