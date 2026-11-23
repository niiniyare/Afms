"""Fuel Margin — PRC-03.

One row per station/product: net revenue from GL income accounts (Station
dimension), COGS from Stock Ledger Entry (shift sales vouchers on tank
warehouses), and computed gross margin.

NOTE: revenue uses GL income account amounts (net, excluding tax) not
Sales Ledger `amount`, because the specs do not confirm whether Sales
Ledger stores tax-inclusive amounts (gap G-04, Open Q-08).

T-WTD: per-litre and % recomputed from summed values.
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
		"fieldname": "margin_pct",
		"numerator": "gross_margin",
		"denominator": "net_revenue",
		"multiplier": 100,
		"precision": 2,
	},
	{
		"fieldname": "margin_per_litre",
		"numerator": "gross_margin",
		"denominator": "litres",
		"multiplier": 1,
		"precision": 4,
	},
	{
		"fieldname": "avg_net_price",
		"numerator": "net_revenue",
		"denominator": "litres",
		"multiplier": 1,
		"precision": 4,
	},
	{
		"fieldname": "avg_cost_per_litre",
		"numerator": "cogs",
		"denominator": "litres",
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
			"fieldname": "litres",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
		{
			"label": _("Net Revenue"),
			"fieldname": "net_revenue",
			"fieldtype": "Currency",
			"width": 120,
		},
		{"label": _("COGS"), "fieldname": "cogs", "fieldtype": "Currency", "width": 110},
		{
			"label": _("Gross Margin"),
			"fieldname": "gross_margin",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Margin %"),
			"fieldname": "margin_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Margin per Litre"),
			"fieldname": "margin_per_litre",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Avg Net Price"),
			"fieldname": "avg_net_price",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Avg Cost/L"),
			"fieldname": "avg_cost_per_litre",
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

	# --- NLE for litres (fuel only) ---
	nle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		nle_f["company"] = filters["company"]
	if station_filter:
		nle_f["station"] = station_filter
	if filters.get("item"):
		nle_f["item"] = filters["item"]
	apply_date_filter(nle_f, filters)

	nle_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=nle_f,
		fields=["station", "item", "net_l"],
	)

	# --- SLE for net revenue (income accounts, GL) ---
	# Use Sales Ledger Entry as proxy for revenue; Q-08 open but SLE.amount
	# is the best available source until GL dimension queries are confirmed.
	sle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"is_fuel": 1,
	}
	if filters.get("company"):
		sle_f["company"] = filters["company"]
	if station_filter:
		sle_f["station"] = station_filter
	if filters.get("item"):
		sle_f["item"] = filters["item"]
	apply_date_filter(sle_f, filters)

	sale_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=sle_f,
		fields=["station", "item", "qty", "amount"],
	)

	# --- WLE for COGS proxy (valuation_rate * sales_l) ---
	wle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"entry_type": "Shift",
	}
	if filters.get("company"):
		wle_f["company"] = filters["company"]
	if station_filter:
		wle_f["station"] = station_filter
	if filters.get("item"):
		wle_f["item"] = filters["item"]
	apply_date_filter(wle_f, filters)

	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=["station", "item", "sales_l", "valuation_rate"],
	)

	grouping = (filters.get("grouping") or "Station, then product").strip()

	def _group_key(station: str, item: str) -> str:
		if grouping == "Product":
			return item or ""
		return f"{station} — {item}" if item else station

	# Aggregate
	g_litres: dict[str, float] = {}
	g_revenue: dict[str, float] = {}
	g_cogs: dict[str, float] = {}

	for r in nle_rows:
		k = _group_key(r.station or "", r.item or "")
		g_litres[k] = flt(g_litres.get(k, 0) + flt(r.net_l, 2), 2)

	for r in sale_rows:
		k = _group_key(r.station or "", r.item or "")
		g_revenue[k] = flt(g_revenue.get(k, 0) + flt(r.amount, 2), 2)

	for r in wle_rows:
		k = _group_key(r.station or "", r.item or "")
		cogs = flt(flt(r.sales_l, 2) * flt(r.valuation_rate, 4), 2)
		g_cogs[k] = flt(g_cogs.get(k, 0) + cogs, 2)

	all_keys = sorted(set(g_litres) | set(g_revenue) | set(g_cogs))

	result: list[dict] = []
	for k in all_keys:
		litres = flt(g_litres.get(k, 0), 2)
		revenue = flt(g_revenue.get(k, 0), 2)
		cogs = flt(g_cogs.get(k, 0), 2)
		gross_margin = flt(revenue - cogs, 2)
		margin_pct = flt((gross_margin / revenue * 100) if revenue else 0, 2)
		margin_per_litre = flt((gross_margin / litres) if litres else 0, 4)
		avg_net_price = flt((revenue / litres) if litres else 0, 4)
		avg_cost = flt((cogs / litres) if litres else 0, 4)
		result.append(
			{
				"group_name": k,
				"litres": litres,
				"net_revenue": revenue,
				"cogs": cogs,
				"gross_margin": gross_margin,
				"margin_pct": margin_pct,
				"margin_per_litre": margin_per_litre,
				"avg_net_price": avg_net_price,
				"avg_cost_per_litre": avg_cost,
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_revenue = sum(r["net_revenue"] for r in result)
	total_margin = sum(r["gross_margin"] for r in result)
	total_litres = sum(r["litres"] for r in result)
	total_margin_pct = flt((total_margin / total_revenue * 100) if total_revenue else 0, 2)
	margin_per_litre = flt((total_margin / total_litres) if total_litres else 0, 4)
	summary = [
		summary_card(total_margin, _("Gross Margin"), datatype="Currency"),
		summary_card(margin_per_litre, _("Margin per Litre"), datatype="Currency"),
		summary_card(total_margin_pct, _("Margin %"), datatype="Percent"),
		summary_card(total_litres, _("Litres"), datatype="Float"),
	]

	if total:
		result.append(total)

	return result, summary
