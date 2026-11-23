"""Realised Margin after Losses — PRC-04.

What is left of the gross margin after tank variance costs, own use costs
and uncovered delivery shortages.

Gross margin figures come from the same aggregation as PRC-03 (Fuel Margin);
loss costs come from Wetstock Ledger Entry fields.

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
		"fieldname": "realised_per_litre",
		"numerator": "realised_margin",
		"denominator": "litres",
		"multiplier": 1,
		"precision": 4,
	},
	{
		"fieldname": "losses_pct_of_gross",
		"numerator": "_total_losses",
		"denominator": "gross_margin",
		"multiplier": 100,
		"precision": 2,
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
			"width": 90,
		},
		{
			"label": _("Gross Margin"),
			"fieldname": "gross_margin",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Tank Variance Cost"),
			"fieldname": "variance_cost",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Own Use Cost"),
			"fieldname": "own_use_cost",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Delivery Shortage"),
			"fieldname": "delivery_shortage",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Realised Margin"),
			"fieldname": "realised_margin",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Realised per Litre"),
			"fieldname": "realised_per_litre",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Losses % of Gross"),
			"fieldname": "losses_pct_of_gross",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 120,
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

	def _base_f() -> dict:
		f: dict = {
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
		}
		if filters.get("company"):
			f["company"] = filters["company"]
		if station_filter:
			f["station"] = station_filter
		if filters.get("item"):
			f["item"] = filters["item"]
		apply_date_filter(f, filters)
		return f

	# Litres from NLE
	nle_rows = frappe.get_all(
		"Nozzle Ledger Entry",
		filters=_base_f(),
		fields=["station", "item", "net_l"],
	)

	# Revenue from SLE
	sle_f = {**_base_f(), "is_fuel": 1}
	sale_rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=sle_f,
		fields=["station", "item", "qty", "amount"],
	)

	# WLE for cogs, variance cost, own use
	wle_f = {**_base_f(), "entry_type": "Shift"}
	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=["station", "item", "sales_l", "valuation_rate", "variance_value", "own_use_l"],
	)

	# WLE delivery shortages
	dlv_f = {**_base_f(), "entry_type": "Delivery"}
	dlv_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=dlv_f,
		fields=["station", "item", "delivery_variance_l", "valuation_rate"],
	)

	def _key(s: str, i: str) -> str:
		return f"{s}|{i}"

	g_litres: dict[str, float] = {}
	g_revenue: dict[str, float] = {}
	g_cogs: dict[str, float] = {}
	g_variance_cost: dict[str, float] = {}
	g_own_use_cost: dict[str, float] = {}
	g_delivery_shortage: dict[str, float] = {}

	for r in nle_rows:
		k = _key(r.station or "", r.item or "")
		g_litres[k] = flt(g_litres.get(k, 0) + flt(r.net_l, 2), 2)

	for r in sale_rows:
		k = _key(r.station or "", r.item or "")
		g_revenue[k] = flt(g_revenue.get(k, 0) + flt(r.amount, 2), 2)

	for r in wle_rows:
		k = _key(r.station or "", r.item or "")
		rate = flt(r.valuation_rate, 4)
		g_cogs[k] = flt(g_cogs.get(k, 0) + flt(r.sales_l, 2) * rate, 2)
		# variance_value is signed; losses are negative
		g_variance_cost[k] = flt(g_variance_cost.get(k, 0) + abs(flt(r.variance_value, 2)), 2)
		g_own_use_cost[k] = flt(g_own_use_cost.get(k, 0) + flt(r.own_use_l, 2) * rate, 2)

	for r in dlv_rows:
		k = _key(r.station or "", r.item or "")
		dlv_var = flt(r.delivery_variance_l, 2)
		if dlv_var < 0:
			rate = flt(r.valuation_rate, 4)
			g_delivery_shortage[k] = flt(g_delivery_shortage.get(k, 0) + abs(dlv_var) * rate, 2)

	all_keys = sorted(set(g_litres) | set(g_revenue))

	result: list[dict] = []
	for k in all_keys:
		station, item = k.split("|", 1)
		litres = flt(g_litres.get(k, 0), 2)
		revenue = flt(g_revenue.get(k, 0), 2)
		cogs = flt(g_cogs.get(k, 0), 2)
		gross_margin = flt(revenue - cogs, 2)
		variance_cost = flt(g_variance_cost.get(k, 0), 2)
		own_use_cost = flt(g_own_use_cost.get(k, 0), 2)
		delivery_shortage = flt(g_delivery_shortage.get(k, 0), 2)
		total_losses = flt(variance_cost + own_use_cost + delivery_shortage, 2)
		realised = flt(gross_margin - total_losses, 2)
		realised_per_litre = flt((realised / litres) if litres else 0, 4)
		losses_pct = flt((total_losses / gross_margin * 100) if gross_margin else 0, 2)
		result.append(
			{
				"group_name": f"{station} — {item}" if item else station,
				"litres": litres,
				"gross_margin": gross_margin,
				"variance_cost": variance_cost,
				"own_use_cost": own_use_cost,
				"delivery_shortage": delivery_shortage,
				"realised_margin": realised,
				"realised_per_litre": realised_per_litre,
				"losses_pct_of_gross": losses_pct,
				"_total_losses": total_losses,
			}
		)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_realised = sum(r["realised_margin"] for r in result)
	total_gross = sum(r["gross_margin"] for r in result)
	summary = [
		summary_card(total_gross, _("Gross Margin"), datatype="Currency"),
		summary_card(total_realised, _("Realised Margin"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
