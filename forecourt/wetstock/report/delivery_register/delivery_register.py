"""Delivery Register — DLV-01.

One row per submitted Purchase Receipt (fuel), showing delivery details,
dip-based litres, GRN variance and shift link.

T-ADD: litres, variance_l summed in total row.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_date_filter,
	apply_station_permission,
	summary_card,
	total_row_add,
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
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("GRN"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
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
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
		},
		{
			"label": _("Transporter"),
			"fieldname": "transporter",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
		},
		{
			"label": _("Driver"),
			"fieldname": "driver",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Product"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 110,
		},
		{
			"label": _("Invoiced L"),
			"fieldname": "invoiced_l",
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
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
			"label": _("Truck / Ref"),
			"fieldname": "truck",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift",
			"fieldtype": "Link",
			"options": "Forecourt Shift",
			"width": 160,
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
	apply_date_filter(wle_f, filters)

	wle_rows = frappe.get_all(
		"Wetstock Ledger Entry",
		filters=wle_f,
		fields=[
			"station",
			"item",
			"voucher_no",
			"posting_date",
			"receipt_l",
			"dip_l",
			"delivery_variance_l",
			"supplier",
			"transporter",
			"driver",
			"fms_forecourt_shift",
		],
		order_by="posting_date asc, voucher_no asc",
	)

	# Enrich with truck ref from Purchase Receipt custom field
	pr_names = list({r.voucher_no for r in wle_rows if r.voucher_no})
	truck_map: dict[str, str] = {}
	if pr_names:
		prs = frappe.get_all(
			"Purchase Receipt",
			filters={"name": ["in", pr_names]},
			fields=["name", "fms_truck"],
		)
		truck_map = {pr.name: pr.fms_truck or "" for pr in prs}

	# Apply supplier/transporter filters if set
	supplier_f = filters.get("supplier")
	transporter_f = filters.get("transporter")

	result: list[dict] = []
	for r in wle_rows:
		if supplier_f and r.supplier != supplier_f:
			continue
		if transporter_f and r.transporter != transporter_f:
			continue
		invoiced = flt(r.receipt_l, 2)
		dip = flt(r.dip_l, 2)
		var = flt(r.delivery_variance_l, 2)
		var_pct = flt((var / invoiced * 100) if invoiced else 0, 2)
		result.append(
			{
				"posting_date": r.posting_date,
				"name": r.voucher_no,
				"station": r.station,
				"supplier": r.supplier,
				"transporter": r.transporter,
				"driver": r.driver,
				"item": r.item,
				"invoiced_l": invoiced,
				"dip_l": dip,
				"variance_l": var,
				"variance_pct": var_pct,
				"truck": truck_map.get(r.voucher_no or "", ""),
				"shift": r.fms_forecourt_shift,
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_invoiced = sum(r["invoiced_l"] for r in result)
	total_var = sum(r["variance_l"] for r in result)
	summary = [
		summary_card(len(result), _("Deliveries"), datatype="Int"),
		summary_card(total_invoiced, _("Total Invoiced L"), datatype="Float"),
		summary_card(total_var, _("Total Variance L"), datatype="Float"),
	]

	if total:
		result.append(total)

	return result, summary
