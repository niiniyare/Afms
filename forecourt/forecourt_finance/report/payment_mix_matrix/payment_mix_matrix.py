"""Payment Mix Matrix — FMS-H03. Pivot: product x payment type."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

_PAYMENT_TYPES = ["Cash", "Mobile Money", "Card", "Credit", "Voucher"]


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	cols = [
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 140},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
	]
	for pt in _PAYMENT_TYPES:
		cols.append(
			{
				"label": _(pt),
				"fieldname": pt.lower().replace(" ", "_"),
				"fieldtype": "Currency",
				"width": 110,
			}
		)
	cols.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 120})
	return cols


def _data(filters):
	f = {"is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("from_date") and filters.get("to_date"):
		f["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	rows = frappe.get_all(
		"Sales Ledger Entry",
		filters=f,
		fields=["item", "station", "payment_type", "amount"],
	)

	key_map: dict[tuple, dict] = {}
	for row in rows:
		key = (row.item or "", row.station or "")
		if key not in key_map:
			rec = {"item": row.item, "station": row.station, "total": 0.0}
			for pt in _PAYMENT_TYPES:
				rec[pt.lower().replace(" ", "_")] = 0.0
			key_map[key] = rec

		d = key_map[key]
		amt = flt(row.amount, 2)
		d["total"] = flt(d["total"] + amt, 2)
		pt_key = (row.payment_type or "").lower().replace(" ", "_")
		if pt_key in d:
			d[pt_key] = flt(d[pt_key] + amt, 2)

	return sorted(key_map.values(), key=lambda r: (r["station"] or "", r["item"] or ""))
