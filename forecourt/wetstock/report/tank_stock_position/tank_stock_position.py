"""Tank Stock Position — FMS-H04. Current stock per tank from the latest Wetstock Ledger Entry."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{"label": _("Tank"), "fieldname": "tank", "fieldtype": "Link", "options": "Fuel Tank", "width": 120},
		{"label": _("Product"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 110},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Last Shift"),
			"fieldname": "forecourt_shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
		},
		{"label": _("Last Dip L"), "fieldname": "dip_l", "fieldtype": "Float", "precision": 3, "width": 100},
		{
			"label": _("Expected L"),
			"fieldname": "expected_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Variance L"),
			"fieldname": "variance_l",
			"fieldtype": "Float",
			"precision": 3,
			"width": 100,
		},
		{
			"label": _("Var %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 80,
		},
		{"label": _("Last Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
	]


def _data(filters):
	f = {"entry_type": "Shift", "is_cancelled": 0, "superseded_by": ["is", "not set"]}
	if filters.get("station"):
		f["station"] = filters["station"]
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("tank"):
		f["tank"] = filters["tank"]

	# Get latest Shift entry per tank (most recent posting_date + shift)
	rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=f,
		fields=[
			"tank",
			"item",
			"station",
			"forecourt_shift",
			"posting_date",
			"dip_l",
			"expected_l",
			"variance_l",
			"variance_pct",
		],
		order_by="tank asc, posting_date desc, forecourt_shift desc",
	)

	seen: set[str] = set()
	result = []
	for row in rows:
		tank = row.tank or ""
		if tank in seen:
			continue
		seen.add(tank)
		result.append(
			{
				"tank": row.tank,
				"item": row.item,
				"station": row.station,
				"forecourt_shift": row.forecourt_shift,
				"posting_date": row.posting_date,
				"dip_l": flt(row.dip_l, 3),
				"expected_l": flt(row.expected_l, 3),
				"variance_l": flt(row.variance_l, 3),
				"variance_pct": flt(row.variance_pct, 2),
			}
		)

	return sorted(result, key=lambda r: (r["station"] or "", r["tank"] or ""))
