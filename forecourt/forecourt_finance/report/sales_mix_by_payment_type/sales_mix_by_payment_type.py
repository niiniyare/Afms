"""Sales Mix by Payment Type — SAL-05.

One row per station or cashier: what share of sales was cash, mobile money,
card, credit and voucher. A cashier with far less mobile money than
colleagues may be redirecting payments (fms.md 7.4).

T-RANK: network-average row; deviation = absolute distance from network %.
Flag threshold is a filter (default 15 points, Open Q-06).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_rank,
	validate_date_range,
)

_PAYMENT_TYPES = ("Cash", "Mobile Money", "Card", "Credit", "Voucher")


def execute(filters: dict | None = None):
	filters = filters or {}
	err = validate_date_range(filters.get("from_date"), filters.get("to_date"))
	if err:
		frappe.throw(err)
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{"label": _("Group"), "fieldname": "group_name", "fieldtype": "Data", "width": 160},
		{
			"label": _("Sales"),
			"fieldname": "total_sales",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Cash %"),
			"fieldname": "cash_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
		{
			"label": _("Mobile %"),
			"fieldname": "mobile_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
		{
			"label": _("Card %"),
			"fieldname": "card_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
		{
			"label": _("Credit %"),
			"fieldname": "credit_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
		{
			"label": _("Voucher %"),
			"fieldname": "voucher_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 80,
		},
		{
			"label": _("Network Mobile %"),
			"fieldname": "network_mobile_pct",
			"fieldtype": "Percent",
			"precision": 1,
			"width": 130,
		},
		{
			"label": _("Deviation (pts)"),
			"fieldname": "deviation_pts",
			"fieldtype": "Float",
			"precision": 1,
			"width": 110,
		},
		{"label": _("Flag"), "fieldname": "flag", "fieldtype": "Data", "width": 100},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	apply_date_filter(f, filters)
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	level = (filters.get("level") or "Station").strip()
	group_field = "cashier" if level == "Cashier" else "station"

	entries = frappe.get_all(
		"Sales Ledger Entry",
		filters=f,
		fields=[group_field, "payment_type", "amount"],
	)

	# Aggregate per group + payment_type
	group_map: dict[str, dict] = {}
	for e in entries:
		gv = e.get(group_field) or ""
		if gv not in group_map:
			group_map[gv] = {
				"group_name": gv,
				"total_sales": 0.0,
				"Cash": 0.0,
				"Mobile Money": 0.0,
				"Card": 0.0,
				"Credit": 0.0,
				"Voucher": 0.0,
			}
		gm = group_map[gv]
		amount = flt(e.amount, 2)
		gm["total_sales"] = flt(gm["total_sales"] + amount, 2)
		pt = e.payment_type or "Cash"
		if pt in _PAYMENT_TYPES:
			gm[pt] = flt(gm[pt] + amount, 2)

	# Network mobile % for deviation
	total_mobile = sum(gm["Mobile Money"] for gm in group_map.values())
	total_all = sum(gm["total_sales"] for gm in group_map.values())
	network_mobile_pct = flt((total_mobile / total_all * 100) if total_all else 0, 1)

	flag_threshold = flt(filters.get("flag_threshold_pct") or 15, 1)

	result: list[dict] = []
	for gm in sorted(group_map.values(), key=lambda x: x["group_name"]):
		tot = flt(gm["total_sales"], 2)
		if not tot:
			continue

		def pct(pt: str) -> float:
			return flt((flt(gm[pt], 2) / tot * 100) if tot else 0, 1)

		mobile_pct = pct("Mobile Money")
		deviation = flt(mobile_pct - network_mobile_pct, 1)
		flag = "Low Mobile" if deviation < -flag_threshold else ""

		result.append(
			{
				"group_name": gm["group_name"],
				"total_sales": tot,
				"cash_pct": pct("Cash"),
				"mobile_pct": mobile_pct,
				"card_pct": pct("Card"),
				"credit_pct": pct("Credit"),
				"voucher_pct": pct("Voucher"),
				"network_mobile_pct": network_mobile_pct,
				"deviation_pts": deviation,
				"flag": flag,
			}
		)

	cols = _columns()
	rank_row = total_row_rank(result, cols) if result else None
	if rank_row:
		result.append(rank_row)

	flagged = sum(1 for r in result if r.get("flag"))
	summary = [
		summary_card(len(result), _("Groups"), datatype="Int"),
		summary_card(
			flagged,
			_("Flagged (Low Mobile)"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
		summary_card(network_mobile_pct, _("Network Mobile %"), datatype="Percent"),
	]

	return result, summary
