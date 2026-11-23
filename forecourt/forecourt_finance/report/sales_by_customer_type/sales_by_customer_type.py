"""Sales by Customer Type — SAL-07.

One row per customer type (Walk-in / Credit / Voucher), or grouped by
customer group, customer, or station: litres, amount, share %, avg price,
customer count.

T-WTD: share % and avg price recomputed from summed values.
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
		"fieldname": "share_pct",
		"numerator": "amount",
		"denominator": "_total_amount",
		"multiplier": 100,
		"precision": 1,
	},
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
		{"label": _("Group"), "fieldname": "group_name", "fieldtype": "Data", "width": 180},
		{
			"label": _("Litres"),
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
			"label": _("Share %"),
			"fieldname": "share_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 90,
		},
		{
			"label": _("Avg Price"),
			"fieldname": "avg_price",
			"fieldtype": "Currency",
			"width": 100,
		},
		{"label": _("Customers"), "fieldname": "customer_count", "fieldtype": "Int", "width": 90},
	]


def _customer_type(payment_type: str | None) -> str:
	"""Classify a Sales Ledger Entry by customer type from payment_type."""
	pt = (payment_type or "").strip()
	if pt == "Credit":
		return "Credit"
	if pt == "Voucher":
		return "Voucher"
	return "Walk-in"


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("item"):
		f["item"] = filters["item"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	grouping = (filters.get("grouping") or "Customer Type").strip()
	fields = ["payment_type", "customer", "qty", "amount", "station"]
	if grouping == "Customer Group":
		fields.append("customer")  # will join to Customer below

	entries = frappe.get_all(
		"Sales Ledger Entry",
		filters=f,
		fields=fields,
	)

	# Optionally filter by customer_group
	requested_cg = filters.get("customer_group")
	customer_groups: dict[str, str] = {}
	if requested_cg or grouping == "Customer Group":
		customers = list({e.customer for e in entries if e.customer})
		if customers:
			cust_rows = frappe.get_all(
				"Customer",
				filters={"name": ["in", customers]},
				fields=["name", "customer_group"],
			)
			for c in cust_rows:
				if c.customer_group:
					customer_groups[c.name] = c.customer_group

		if requested_cg:
			entries = [e for e in entries if customer_groups.get(e.customer or "") == requested_cg]

	total_amount = flt(sum(flt(e.amount, 2) for e in entries), 2)

	# Group
	group_map: dict[str, dict] = {}
	for e in entries:
		if grouping == "Customer Type":
			gv = _customer_type(e.payment_type)
		elif grouping == "Customer Group":
			gv = customer_groups.get(e.customer or "") or "—"
		elif grouping == "Customer":
			gv = e.customer or "Walk-in"
		else:  # Station
			gv = e.station or ""

		if gv not in group_map:
			group_map[gv] = {"group_name": gv, "qty": 0.0, "amount": 0.0, "customers": set()}
		gm = group_map[gv]
		gm["qty"] = flt(gm["qty"] + flt(e.qty, 2), 2)
		gm["amount"] = flt(gm["amount"] + flt(e.amount, 2), 2)
		if e.customer:
			gm["customers"].add(e.customer)

	result: list[dict] = []
	for gm in sorted(group_map.values(), key=lambda x: -x["amount"]):
		qty = flt(gm["qty"], 2)
		amount = flt(gm["amount"], 2)
		share_pct = flt((amount / total_amount * 100) if total_amount else 0, 1)
		avg_price = flt((amount / qty) if qty else 0, 4)
		result.append(
			{
				"group_name": gm["group_name"],
				"qty": qty,
				"amount": amount,
				"share_pct": share_pct,
				"avg_price": avg_price,
				"customer_count": len(gm["customers"]),
				"_total_amount": total_amount,  # used by T-WTD computed
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	summary = [
		summary_card(len(result), _("Groups"), datatype="Int"),
		summary_card(total_amount, _("Total Sales"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
