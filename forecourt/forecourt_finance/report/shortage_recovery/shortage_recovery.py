"""Shortage Recovery — CSH-06.

Per-cashier summary of shortages charged, recovered and still outstanding.
Source: Cashier Ledger Entry (difference < 0) with resolution fields.

T-ADD totals.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today

from forecourt.reports.common import (
	summary_card,
	total_row_add,
)

_RECOVERY_ACTIONS = {"Recovered - Cash", "Recovery - Cash"}
_WRITEOFF_ACTIONS = {"Write-off", "Written Off"}


def execute(filters: dict | None = None):
	filters = filters or {}
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Cashier"),
			"fieldname": "cashier",
			"fieldtype": "Link",
			"options": "Employee",
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
			"label": _("Shortages"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Charged"),
			"fieldname": "charged",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Recovered Cash"),
			"fieldname": "recovered_cash",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Written Off"),
			"fieldname": "written_off",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"difference": ["<", 0],
	}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("cashier"):
		f["cashier"] = filters["cashier"]
	as_at = filters.get("as_at") or today()
	f["posting_date"] = ["<=", as_at]

	rows = frappe.get_all(
		"Cashier Ledger Entry",
		filters=f,
		fields=["cashier", "station", "posting_date", "difference", "resolution_action", "resolution_amount"],
		order_by="cashier asc, posting_date asc",
	)

	# Aggregate per cashier + station
	cashier_map: dict[tuple, dict] = {}
	for r in rows:
		key = (r.cashier or "", r.station or "")
		if key not in cashier_map:
			cashier_map[key] = {
				"cashier": r.cashier,
				"station": r.station,
				"count": 0,
				"charged": 0.0,
				"recovered_cash": 0.0,
				"written_off": 0.0,
			}
		cm = cashier_map[key]
		cm["count"] += 1
		cm["charged"] = flt(cm["charged"] + abs(flt(r.difference, 2)), 2)
		action = (r.resolution_action or "").strip()
		amount = flt(r.resolution_amount, 2)
		if action in _RECOVERY_ACTIONS:
			cm["recovered_cash"] = flt(cm["recovered_cash"] + amount, 2)
		elif action in _WRITEOFF_ACTIONS:
			cm["written_off"] = flt(cm["written_off"] + amount, 2)

	result = []
	for cm in sorted(cashier_map.values(), key=lambda x: (x["cashier"] or "", x["station"] or "")):
		outstanding = flt(cm["charged"] - cm["recovered_cash"] - cm["written_off"], 2)
		if filters.get("only_outstanding") and outstanding <= 0:
			continue
		cm["outstanding"] = outstanding
		result.append(cm)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_charged = sum(r["charged"] for r in result)
	total_outstanding = sum(r["outstanding"] for r in result)
	cashiers_with_balance = sum(1 for r in result if r["outstanding"] > 0)

	summary = [
		summary_card(total_charged, _("Total Charged"), datatype="Currency"),
		summary_card(
			total_outstanding,
			_("Outstanding"),
			datatype="Currency",
			indicator="Orange" if total_outstanding > 0 else "Green",
		),
		summary_card(cashiers_with_balance, _("Cashiers with Balance"), datatype="Int"),
	]

	if total:
		result.append(total)

	return result, summary
