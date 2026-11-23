"""Tank Transfer Register — WET-07.

One row per submitted Tank Transfer: when it happened, which tanks,
product, volume, reason, and the Stock Entry created on submit.

T-REG: litres.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_reg,
	validate_date_range,
)


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
			"label": _("Transferred At"),
			"fieldname": "transferred_at",
			"fieldtype": "Datetime",
			"width": 130,
		},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("From Tank"),
			"fieldname": "from_tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 130,
		},
		{
			"label": _("To Tank"),
			"fieldname": "to_tank",
			"fieldtype": "Link",
			"options": "Fuel Tank",
			"width": 130,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Litres"),
			"fieldname": "volume_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 90,
		},
		{"label": _("Reason"), "fieldname": "reason", "fieldtype": "Data", "width": 180},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 140,
		},
		{
			"label": _("Prepared By"),
			"fieldname": "owner",
			"fieldtype": "Link",
			"options": "User",
			"width": 140,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {"docstatus": 1}
	if filters.get("company"):
		f["company"] = filters["company"]
	if filters.get("station"):
		f["station"] = filters["station"]
	apply_date_filter(f, filters, date_field="transferred_at")
	err = apply_station_permission(f, filters)
	if err:
		return [], []

	# Tank filter may apply to either from_tank or to_tank
	tank = filters.get("tank")

	transfers = frappe.get_all(
		"Tank Transfer",
		filters=f,
		fields=[
			"name",
			"station",
			"from_tank",
			"to_tank",
			"volume_l",
			"transferred_at",
			"reason",
			"stock_entry",
			"owner",
		],
		order_by="transferred_at asc",
	)

	# Enrich with item from from_tank
	tank_items: dict[str, str] = {}
	all_tanks = list(
		{t.from_tank for t in transfers if t.from_tank} | {t.to_tank for t in transfers if t.to_tank}
	)
	if all_tanks:
		tank_docs = frappe.get_all("Fuel Tank", filters={"name": ["in", all_tanks]}, fields=["name", "item"])
		for td in tank_docs:
			if td.item:
				tank_items[td.name] = td.item

	result: list[dict] = []
	for t in transfers:
		if tank and t.from_tank != tank and t.to_tank != tank:
			continue
		result.append(
			{
				"transferred_at": t.transferred_at,
				"station": t.station,
				"from_tank": t.from_tank,
				"to_tank": t.to_tank,
				"item": tank_items.get(t.from_tank or "", ""),
				"volume_l": flt(t.volume_l, 2),
				"reason": t.reason or "",
				"stock_entry": t.stock_entry,
				"owner": t.owner,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="transferred_at") if result else {}

	total_litres = sum(r["volume_l"] for r in result)
	summary = [
		summary_card(len(result), _("Transfers"), datatype="Int"),
		summary_card(total_litres, _("Total Litres Transferred"), datatype="Float"),
	]

	if total:
		result.append(total)

	return result, summary
