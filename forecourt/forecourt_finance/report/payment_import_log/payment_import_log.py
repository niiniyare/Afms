"""Payment Import Log — PAY-05.

One row per Payment Import Batch, showing provider, status and
row-level match counts. Company-level (no station filter).

T-REG: count rows.
"""

from __future__ import annotations

import frappe
from frappe import _

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
			"label": _("Batch"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Payment Import Batch",
			"width": 160,
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Provider"),
			"fieldname": "provider",
			"fieldtype": "Link",
			"options": "Payment Provider",
			"width": 140,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Total Rows"),
			"fieldname": "total_rows",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Matched"),
			"fieldname": "matched_rows",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Unmatched"),
			"fieldname": "unmatched_rows",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Errors"),
			"fieldname": "error_rows",
			"fieldtype": "Int",
			"width": 70,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []

	pib_f: dict = {}
	if filters.get("company"):
		pib_f["company"] = filters["company"]
	if filters.get("provider"):
		pib_f["provider"] = filters["provider"]
	if filters.get("status"):
		pib_f["status"] = filters["status"]
	apply_date_filter(pib_f, filters)

	pib_rows = frappe.get_all(
		"Payment Import Batch",
		filters=pib_f,
		fields=[
			"name",
			"posting_date",
			"provider",
			"status",
			"total_rows",
			"matched_rows",
			"unmatched_rows",
			"error_rows",
		],
		order_by="posting_date desc",
	)

	result = [
		{
			"name": r.name,
			"posting_date": r.posting_date,
			"provider": r.provider,
			"status": r.status or "",
			"total_rows": r.total_rows or 0,
			"matched_rows": r.matched_rows or 0,
			"unmatched_rows": r.unmatched_rows or 0,
			"error_rows": r.error_rows or 0,
		}
		for r in pib_rows
	]

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	total_matched = sum(r["matched_rows"] for r in result)
	total_unmatched = sum(r["unmatched_rows"] for r in result)
	summary = [
		summary_card(len(result), _("Batches"), datatype="Int"),
		summary_card(total_matched, _("Matched Rows"), datatype="Int"),
		summary_card(
			total_unmatched,
			_("Unmatched Rows"),
			datatype="Int",
			indicator="Orange" if total_unmatched else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
