"""Card Settlement — PAY-04.

One row per Sales Ledger Entry with payment_type Card.
Provider sourced from mode_of_payment; terminal from matched
Shift Collection.

T-ADD: qty, amount summed.
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
			"label": _("Provider"),
			"fieldname": "provider",
			"fieldtype": "Link",
			"options": "Payment Provider",
			"width": 130,
		},
		{
			"label": _("Terminal"),
			"fieldname": "terminal",
			"fieldtype": "Data",
			"width": 110,
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
			"fieldname": "qty",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
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

	sle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"payment_type": "Card",
	}
	if filters.get("company"):
		sle_f["company"] = filters["company"]
	if station_filter:
		sle_f["station"] = station_filter
	apply_date_filter(sle_f, filters)

	sle_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=sle_f,
		fields=[
			"posting_date",
			"station",
			"cashier",
			"item",
			"qty",
			"amount",
			"fms_forecourt_shift",
			"mode_of_payment",
		],
		order_by="posting_date asc",
	)

	# Enrich from Shift Collection for provider + terminal
	shift_names = list({r.fms_forecourt_shift for r in sle_rows if r.fms_forecourt_shift})
	col_map: dict[tuple, dict] = {}
	if shift_names:
		coll_rows = frappe.get_all(
			"Shift Collection",
			filters={
				"parent": ["in", shift_names],
				"collection_type": "Card",
			},
			fields=["parent", "cashier", "provider", "till_or_terminal"],
		)
		for c in coll_rows:
			key = (c.parent or "", c.cashier or "")
			col_map.setdefault(key, c)

	provider_f = filters.get("provider")

	result: list[dict] = []
	for r in sle_rows:
		key = (r.fms_forecourt_shift or "", r.cashier or "")
		coll = col_map.get(key)
		provider = (coll.provider if coll else None) or r.mode_of_payment or ""
		terminal = (coll.till_or_terminal if coll else None) or ""

		if provider_f and provider != provider_f:
			continue

		result.append(
			{
				"posting_date": r.posting_date,
				"station": r.station,
				"cashier": r.cashier,
				"provider": provider,
				"terminal": terminal,
				"item": r.item,
				"qty": flt(r.qty, 2),
				"amount": flt(r.amount, 2),
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(len(result), _("Transactions"), datatype="Int"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
