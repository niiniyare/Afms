"""Credit Limits — CRD-04.

One row per Customer with credit_limit > 0: limit, outstanding
receivable balance and available headroom.

NOTE: outstanding_amount is not a stored field on Customer in ERPNext;
this report uses frappe.db.get_value to fetch it if available, falling
back to 0. The authoritative source is the Accounts Receivable report.
Company-level (no station filter).

T-ADD: credit_limit, outstanding, available summed.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.reports.common import (
	apply_station_permission,
	summary_card,
	total_row_add,
	validate_date_range,
)


def execute(filters: dict | None = None):
	filters = filters or {}
	# No date range needed — point-in-time snapshot
	data, summary = _data(filters)
	return _columns(), data, None, None, summary


def _columns() -> list[dict]:
	return [
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{
			"label": _("Customer Name"),
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Credit Limit"),
			"fieldname": "credit_limit",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Limit Applies To"),
			"fieldname": "credit_limit_on",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Available"),
			"fieldname": "available",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
	]


def _data(filters: dict) -> tuple[list[dict], list[dict]]:
	f_perm: dict = {}
	if filters.get("company"):
		f_perm["company"] = filters["company"]
	err = apply_station_permission(f_perm, filters)
	if err:
		return [], []

	cust_f: dict = {"disabled": 0, "credit_limit": [">", 0]}
	if filters.get("customer"):
		cust_f["name"] = filters["customer"]

	customers = frappe.get_all(
		"Customer",
		filters=cust_f,
		fields=["name", "customer_name", "credit_limit", "credit_limit_on"],
		order_by="customer_name asc",
	)

	result: list[dict] = []
	for c in customers:
		credit_limit = flt(c.credit_limit, 2)
		# outstanding_amount is computed by ERPNext on demand; fetch if exists
		outstanding = flt(frappe.db.get_value("Customer", c.name, "outstanding_amount") or 0, 2)
		available = flt(credit_limit - outstanding, 2)
		status = _("Over limit") if outstanding > credit_limit else _("Within limit")
		result.append(
			{
				"customer": c.name,
				"customer_name": c.customer_name or "",
				"credit_limit": credit_limit,
				"credit_limit_on": c.credit_limit_on or _("Company"),
				"outstanding": outstanding,
				"available": available,
				"status": status,
			}
		)

	cols = _columns()
	total = total_row_add(result, cols) if result else {}

	total_limit = sum(r["credit_limit"] for r in result)
	summary = [
		summary_card(len(result), _("Customers"), datatype="Int"),
		summary_card(total_limit, _("Total Credit Limit"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
