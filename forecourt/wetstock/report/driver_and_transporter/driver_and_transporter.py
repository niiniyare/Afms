"""Driver and Transporter — DLV-03.

Delivery variance grouped by transporter, driver or supplier.
Flags parties with variance rate above threshold.

T-WTD: variance_pct recomputed from summed volumes.
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
		"fieldname": "variance_pct",
		"numerator": "variance_l",
		"denominator": "invoiced_l",
		"multiplier": 100,
		"precision": 2,
	},
]

_FLAG_THRESHOLD_PCT = 1.0  # Open Q: flag if variance > 1% of invoiced


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
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Group By"),
			"fieldname": "group_by_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Deliveries"),
			"fieldname": "deliveries",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Invoiced L"),
			"fieldname": "invoiced_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Dip L"),
			"fieldname": "dip_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Variance %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Flag"),
			"fieldname": "flag",
			"fieldtype": "Data",
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

	wle_f: dict = {
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
		"entry_type": "Delivery",
	}
	if filters.get("company"):
		wle_f["company"] = filters["company"]
	if station_filter:
		wle_f["station"] = station_filter
	if filters.get("item"):
		wle_f["item"] = filters["item"]
	if filters.get("supplier"):
		wle_f["supplier"] = filters["supplier"]
	if filters.get("transporter"):
		wle_f["transporter"] = filters["transporter"]
	apply_date_filter(wle_f, filters)

	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=[
			"supplier",
			"transporter",
			"driver",
			"receipt_l",
			"dip_l",
			"delivery_variance_l",
			"voucher_no",
		],
	)

	group_by = (filters.get("group_by") or "Transporter").strip()

	def _party(r) -> str:
		if group_by == "Driver":
			return r.driver or _("Unknown")
		if group_by == "Supplier":
			return r.supplier or _("Unknown")
		return r.transporter or _("Unknown")

	g_inv: dict[str, float] = {}
	g_dip: dict[str, float] = {}
	g_var: dict[str, float] = {}
	g_cnt: dict[str, int] = {}

	# Track unique deliveries per party (voucher_no)
	seen: dict[str, set] = {}

	for r in wle_rows:
		k = _party(r)
		voucher = r.voucher_no or ""
		if k not in seen:
			seen[k] = set()
		if voucher not in seen[k]:
			seen[k].add(voucher)
			g_cnt[k] = g_cnt.get(k, 0) + 1
		g_inv[k] = flt(g_inv.get(k, 0) + flt(r.receipt_l, 2), 2)
		g_dip[k] = flt(g_dip.get(k, 0) + flt(r.dip_l, 2), 2)
		g_var[k] = flt(g_var.get(k, 0) + flt(r.delivery_variance_l, 2), 2)

	result: list[dict] = []
	for k in sorted(g_inv):
		inv = flt(g_inv[k], 2)
		dip = flt(g_dip.get(k, 0), 2)
		var = flt(g_var.get(k, 0), 2)
		var_pct = flt((var / inv * 100) if inv else 0, 2)
		flag = _("High variance") if abs(var_pct) > _FLAG_THRESHOLD_PCT else ""
		result.append(
			{
				"party": k,
				"group_by_type": group_by,
				"deliveries": g_cnt.get(k, 0),
				"invoiced_l": inv,
				"dip_l": dip,
				"variance_l": var,
				"variance_pct": var_pct,
				"flag": flag,
			}
		)

	result.sort(key=lambda r: abs(r["variance_l"]), reverse=True)

	cols = _columns()
	total = total_row_wtd(result, cols, computed=_COMPUTED) if result else {}

	total_inv = sum(r["invoiced_l"] for r in result)
	total_var = sum(r["variance_l"] for r in result)
	flagged = sum(1 for r in result if r["flag"])
	summary = [
		summary_card(total_inv, _("Total Invoiced L"), datatype="Float"),
		summary_card(total_var, _("Total Variance L"), datatype="Float"),
		summary_card(
			flagged,
			_("Flagged Parties"),
			datatype="Int",
			indicator="Orange" if flagged else "Green",
		),
	]

	if total:
		result.append(total)

	return result, summary
