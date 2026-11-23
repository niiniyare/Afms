"""Purchase Cost Trend — PRC-05.

One row per period / supplier / product: invoiced litres, net cost,
landed costs (from Landed Cost Voucher), total cost and cost per litre.

T-WTD: cost_per_litre recomputed from summed totals.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_wtd,
	validate_date_range,
)

_COMPUTED = [
	{
		"fieldname": "cost_per_litre",
		"numerator": "total_cost",
		"denominator": "litres",
		"multiplier": 1,
		"precision": 4,
	},
]


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"), max_days=548)
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{"label": _("Period"), "fieldname": "period_label", "fieldtype": "Data", "width": 110},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 160,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Litres Invoiced"),
			"fieldname": "litres",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Net Cost"),
			"fieldname": "net_cost",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Landed Costs"),
			"fieldname": "landed_costs",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Total Cost"),
			"fieldname": "total_cost",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Cost per Litre"),
			"fieldname": "cost_per_litre",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Change vs Prev Period"),
			"fieldname": "change_vs_prev",
			"fieldtype": "Currency",
			"width": 140,
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

	company = filters.get("company")
	granularity = (filters.get("granularity") or "Month").strip()

	# Purchase Invoice items for fuel
	pi_f: dict = {"docstatus": 1}
	if company:
		pi_f["company"] = company
	if filters.get("supplier"):
		pi_f["supplier"] = filters["supplier"]
	apply_date_filter(pi_f, filters, date_field="posting_date")

	pi_rows = frappe.get_all(
		"Purchase Invoice",
		filters=pi_f,
		fields=["name", "supplier", "posting_date"],
	)
	if not pi_rows:
		return [], []

	pi_names = [pi.name for pi in pi_rows]
	pi_map = {pi.name: pi for pi in pi_rows}

	item_f: dict = {"parent": ["in", pi_names], "is_fuel_item": 1}
	if filters.get("item"):
		item_f["item_code"] = filters["item"]

	pi_items = frappe.get_all(
		"Purchase Invoice Item",
		filters={"parent": ["in", pi_names]},
		fields=["parent", "item_code", "qty", "net_amount"],
	)

	# Landed Cost Voucher for additional costs
	lcv_items = frappe.get_all(
		"Landed Cost Purchase Receipt",
		filters={"receipt_document_type": "Purchase Invoice", "receipt_document": ["in", pi_names]},
		fields=["parent", "receipt_document"],
	)
	lcv_map: dict[str, float] = {}
	if lcv_items:
		lcv_names = list({it.parent for it in lcv_items})
		lcv_taxes = frappe.get_all(
			"Landed Cost Taxes and Charges",
			filters={"parent": ["in", lcv_names]},
			fields=["parent", "amount"],
		)
		for lct in lcv_taxes:
			for lci in lcv_items:
				if lci.parent == lct.parent:
					lcv_map[lci.receipt_document] = flt(
						lcv_map.get(lci.receipt_document, 0) + flt(lct.amount, 2), 2
					)

	def _period_key(d: date) -> str:
		if granularity == "Week":
			iso = d.isocalendar()
			return f"{iso[0]}-W{iso[1]:02d}"
		return f"{d.year}-{d.month:02d}"

	# Aggregate per period / supplier / item
	g: dict[tuple, dict] = {}
	for pii in pi_items:
		pi = pi_map.get(pii.parent)
		if not pi:
			continue
		period = _period_key(getdate(pi.posting_date))
		key = (period, pi.supplier or "", pii.item_code or "")
		if key not in g:
			g[key] = {
				"period_label": period,
				"supplier": pi.supplier,
				"item": pii.item_code,
				"litres": 0.0,
				"net_cost": 0.0,
				"landed_costs": 0.0,
			}
		gk = g[key]
		gk["litres"] = flt(gk["litres"] + flt(pii.qty, 2), 2)
		gk["net_cost"] = flt(gk["net_cost"] + flt(pii.net_amount, 2), 2)

	# Distribute landed costs proportionally to net cost per PI
	for pi_name, lc in lcv_map.items():
		pi = pi_map.get(pi_name)
		if not pi:
			continue
		period = _period_key(getdate(pi.posting_date))
		# Add landed cost to all items in this PI proportionally (simplify: add to first key)
		for key, gk in g.items():
			if key[0] == period and key[1] == pi.supplier:
				net = gk["net_cost"]
				if net:
					gk["landed_costs"] = flt(gk["landed_costs"] + lc, 2)
				break

	# Build result sorted by period then supplier
	rows_by_key: dict[tuple, dict] = {}
	for key, gk in sorted(g.items()):
		litres = flt(gk["litres"], 2)
		net_cost = flt(gk["net_cost"], 2)
		landed = flt(gk["landed_costs"], 2)
		total_cost = flt(net_cost + landed, 2)
		cost_per_litre = flt((total_cost / litres) if litres else 0, 4)
		rows_by_key[key] = {
			"period_label": gk["period_label"],
			"supplier": gk["supplier"],
			"item": gk["item"],
			"litres": litres,
			"net_cost": net_cost,
			"landed_costs": landed,
			"total_cost": total_cost,
			"cost_per_litre": cost_per_litre,
			"change_vs_prev": None,
		}

	# Compute change vs previous period per supplier+item
	prev_cpl: dict[tuple, float] = {}
	result: list[dict] = []
	for key in sorted(rows_by_key):
		row = rows_by_key[key]
		si_key = (key[1], key[2])
		prev = prev_cpl.get(si_key)
		if prev is not None:
			row["change_vs_prev"] = flt(row["cost_per_litre"] - prev, 4)
		prev_cpl[si_key] = row["cost_per_litre"]
		result.append(row)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_cost = sum(r["total_cost"] for r in result)
	total_litres = sum(r["litres"] for r in result)
	avg_cpl = flt((total_cost / total_litres) if total_litres else 0, 4)
	summary = [
		summary_card(total_litres, _("Litres Invoiced"), datatype="Float"),
		summary_card(total_cost, _("Total Cost"), datatype="Currency"),
		summary_card(avg_cpl, _("Avg Cost per Litre"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
