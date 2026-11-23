"""Debt Receipts Register — PAY-06.

One row per Shift Collection of type Debt Receipt: customer,
payment method, provider, reference, amount.

T-ADD: amount summed.
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
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"label": _("Paid By"),
			"fieldname": "paid_by",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Provider"),
			"fieldname": "provider",
			"fieldtype": "Link",
			"options": "Payment Provider",
			"width": 130,
		},
		{
			"label": _("Reference"),
			"fieldname": "reference",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
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

	# Get shifts in range/station
	shift_f: dict = {
		"docstatus": 1,
		"is_cancelled": 0,
	}
	if filters.get("company"):
		shift_f["company"] = filters["company"]
	if station_filter:
		shift_f["station"] = station_filter
	apply_date_filter(shift_f, filters, date_field="shift_date")

	shift_rows = frappe.get_all(
		"Forecourt Shift",
		filters=shift_f,
		fields=["name", "station", "shift_date"],
	)
	if not shift_rows:
		return [], []

	shift_names = [s.name for s in shift_rows]
	shift_info = {s.name: s for s in shift_rows}

	coll_f: dict = {
		"parent": ["in", shift_names],
		"collection_type": "Debt Receipt",
	}
	if filters.get("customer"):
		coll_f["customer"] = filters["customer"]

	coll_rows = frappe.get_all(
		"Shift Collection",
		filters=coll_f,
		fields=[
			"parent",
			"cashier",
			"customer",
			"paid_by",
			"provider",
			"reference",
			"amount",
		],
	)

	result: list[dict] = []
	for c in coll_rows:
		sh = shift_info.get(c.parent)
		result.append(
			{
				"posting_date": sh.shift_date if sh else None,
				"station": sh.station if sh else "",
				"cashier": c.cashier,
				"customer": c.customer,
				"paid_by": c.paid_by or "",
				"provider": c.provider,
				"reference": c.reference or "",
				"amount": flt(c.amount, 2),
			}
		)

	result.sort(key=lambda r: (str(r["posting_date"] or ""), str(r["station"] or "")))

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("Debt Receipts"), datatype="Int"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
