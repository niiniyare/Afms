"""Banking Register — CSH-05.

Every Internal Transfer Payment Entry (safe/in-transit → bank), with
the deposit slip reference and station linkage via fms_forecourt_shift.

T-REG totals: row count + sum of paid_amount.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
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
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{
			"label": _("Payment Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 160,
		},
		{
			"label": _("From Account"),
			"fieldname": "paid_from",
			"fieldtype": "Link",
			"options": "Account",
			"width": 160,
		},
		{
			"label": _("Bank Account"),
			"fieldname": "paid_to",
			"fieldtype": "Link",
			"options": "Account",
			"width": 160,
		},
		{
			"label": _("Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Deposit Slip / Reference"),
			"fieldname": "reference_no",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f: dict = {
		"docstatus": 1,
		"payment_type": "Internal Transfer",
	}
	if filters.get("company"):
		f["company"] = filters["company"]

	# Date range
	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		f["posting_date"] = ["between", [fd, td]]
	elif fd:
		f["posting_date"] = [">=", fd]
	elif td:
		f["posting_date"] = ["<=", td]

	rows = frappe.get_all(
		"Payment Entry",
		filters=f,
		fields=[
			"name",
			"posting_date",
			"paid_amount",
			"paid_from",
			"paid_to",
			"reference_no",
			"remarks",
			"company",
			"fms_forecourt_shift",
		],
		order_by="posting_date asc, name asc",
	)

	# Resolve station from shift
	shift_station: dict[str, str] = {}
	shift_names = [r.fms_forecourt_shift for r in rows if r.get("fms_forecourt_shift")]
	if shift_names:
		for s in frappe.get_all(
			"Forecourt Shift",
			filters={"name": ["in", shift_names]},
			fields=["name", "station"],
		):
			shift_station[s.name] = s.station

	# Apply station permission and filter
	requested_station = filters.get("station")
	permitted: list[str] | None = None
	perm_f: dict = {}
	err = apply_station_permission(perm_f, filters)
	if err:
		return [], []
	if "station" in perm_f:
		permitted = perm_f["station"][1] if isinstance(perm_f.get("station"), list) else [perm_f["station"]]

	result = []
	for r in rows:
		station = shift_station.get(r.fms_forecourt_shift or "", "")
		if requested_station and station != requested_station:
			continue
		if permitted is not None and station and station not in permitted:
			continue
		result.append(
			{
				"posting_date": r.posting_date,
				"station": station,
				"name": r.name,
				"paid_from": r.paid_from,
				"paid_to": r.paid_to,
				"paid_amount": flt(r.paid_amount, 2),
				"reference_no": r.reference_no or "",
				"remarks": r.remarks or "",
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="name") if result else {}

	total_banked = sum(r["paid_amount"] for r in result)
	summary = [
		summary_card(len(result), _("Deposits"), datatype="Int"),
		summary_card(total_banked, _("Total Banked"), datatype="Currency"),
		summary_card(0, _("Unmatched"), datatype="Int", indicator="Green"),
	]

	if total:
		result.append(total)

	return result, summary
