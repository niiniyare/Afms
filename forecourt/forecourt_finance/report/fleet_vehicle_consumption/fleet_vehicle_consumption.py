"""Fleet Vehicle Consumption — CRD-03.

Shift Credit Sale grouped by vehicle + item, showing fills, total
litres, amount and average price per litre.

T-WTD: avg_price recomputed from summed amount / litres.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "avg_price",
		"numerator": "amount",
		"denominator": "qty",
		"multiplier": 1,
		"precision": 4,
	},
]


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
			"label": _("Vehicle"),
			"fieldname": "vehicle",
			"fieldtype": "Link",
			"options": "Customer Vehicle",
			"width": 130,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Fills"),
			"fieldname": "fills",
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"label": _("Qty (L)"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Avg Price"),
			"fieldname": "avg_price",
			"fieldtype": "Currency",
			"width": 100,
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
		fields=["name"],
	)
	if not shift_rows:
		return [], []

	shift_names = [s.name for s in shift_rows]

	cs_f: dict = {"parent": ["in", shift_names]}
	if filters.get("customer"):
		cs_f["customer"] = filters["customer"]
	if filters.get("vehicle"):
		cs_f["vehicle"] = filters["vehicle"]

	cs_rows = frappe.get_all(
		"Shift Credit Sale",
		filters=cs_f,
		fields=["vehicle", "customer", "item", "qty", "amount"],
	)

	g_qty: dict[tuple, float] = {}
	g_amt: dict[tuple, float] = {}
	g_cnt: dict[tuple, int] = {}
	g_cust: dict[tuple, str] = {}

	for cs in cs_rows:
		k = (cs.vehicle or "", cs.item or "")
		g_qty[k] = flt(g_qty.get(k, 0) + flt(cs.qty, 2), 2)
		g_amt[k] = flt(g_amt.get(k, 0) + flt(cs.amount, 2), 2)
		g_cnt[k] = g_cnt.get(k, 0) + 1
		g_cust[k] = cs.customer or ""

	result: list[dict] = []
	for k in sorted(g_qty):
		vehicle, item = k
		qty = flt(g_qty[k], 2)
		amount = flt(g_amt[k], 2)
		avg_price = flt((amount / qty) if qty else 0, 4)
		result.append(
			{
				"vehicle": vehicle,
				"customer": g_cust[k],
				"item": item,
				"fills": g_cnt[k],
				"qty": qty,
				"amount": amount,
				"avg_price": avg_price,
			}
		)

	result.sort(key=lambda r: (r["customer"] or "", r["vehicle"] or ""))

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_qty = sum(r["qty"] for r in result)
	total_amount = sum(r["amount"] for r in result)
	summary = [
		summary_card(total_qty, _("Total Litres"), datatype="Float"),
		summary_card(total_amount, _("Total Amount"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
