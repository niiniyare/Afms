"""Sales Tax Summary — CMP-01.

Tax collected per account and rate from submitted Sales Invoices.
Groups by account_head and rate; computes implied net taxable amount
from base_tax_amount ÷ (rate / 100) for percentage-based taxes.

T-REG: count rows.
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
			"label": _("Tax Account"),
			"fieldname": "account_head",
			"fieldtype": "Link",
			"options": "Account",
			"width": 200,
		},
		{
			"label": _("Rate (%)"),
			"fieldname": "rate",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 90,
		},
		{
			"label": _("Invoices"),
			"fieldname": "invoice_count",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Net Taxable Amount"),
			"fieldname": "net_taxable_amount",
			"fieldtype": "Currency",
			"width": 160,
		},
		{
			"label": _("Tax Amount"),
			"fieldname": "tax_amount",
			"fieldtype": "Currency",
			"width": 140,
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

	# If station filter, resolve SI names via their linked shift
	si_names: list[str] | None = None
	if station_filter:
		shift_f: dict = {"docstatus": 1, "station": station_filter}
		if filters.get("company"):
			shift_f["company"] = filters["company"]
		from forecourt.reports.common import apply_shift_date_filter

		apply_shift_date_filter(shift_f, filters)
		shift_names = frappe.get_all("Forecourt Shift", filters=shift_f, pluck="name")
		if not shift_names:
			return [], []
		si_names = frappe.get_all(
			"Sales Invoice",
			filters={"fms_forecourt_shift": ["in", shift_names], "docstatus": 1},
			pluck="name",
		)
		if not si_names:
			return [], []

	# Build SI filter for non-station path
	if si_names is None:
		si_f: dict = {"docstatus": 1}
		if filters.get("company"):
			si_f["company"] = filters["company"]
		apply_date_filter(si_f, filters)
		si_names = frappe.get_all("Sales Invoice", filters=si_f, pluck="name")
		if not si_names:
			return [], []

	# Fetch tax rows
	tax_f: dict = {"parent": ["in", si_names], "parenttype": "Sales Invoice"}
	if filters.get("tax_account"):
		tax_f["account_head"] = filters["tax_account"]
	# Only percentage-type taxes contribute meaningfully to the summary
	tax_rows = frappe.get_all(
		"Sales Taxes and Charges",
		filters=tax_f,
		fields=["parent", "account_head", "charge_type", "rate", "base_tax_amount"],
	)
	if not tax_rows:
		return [], []

	# Group by account_head + rate
	groups: dict[tuple, dict] = {}
	for t in tax_rows:
		key = (t.account_head or "", flt(t.rate, 2))
		if key not in groups:
			groups[key] = {"invoices": set(), "tax_amount": 0.0}
		groups[key]["invoices"].add(t.parent)
		groups[key]["tax_amount"] += flt(t.base_tax_amount)

	result: list[dict] = []
	for (account_head, rate), g in sorted(groups.items(), key=lambda x: x[0][0]):
		tax_amt = flt(g["tax_amount"], 2)
		net_taxable = flt(tax_amt / (rate / 100), 2) if rate else 0.0
		result.append(
			{
				"account_head": account_head,
				"rate": rate,
				"invoice_count": len(g["invoices"]),
				"net_taxable_amount": net_taxable,
				"tax_amount": tax_amt,
			}
		)

	cols = _columns()
	total = total_row_reg(result, cols, count_label="account_head") if result else {}

	total_tax = flt(sum(r["tax_amount"] for r in result), 2)
	summary = [
		summary_card(len(result), _("Tax Lines"), datatype="Int"),
		summary_card(total_tax, _("Total Tax"), datatype="Currency"),
	]

	if total:
		result.append(total)

	return result, summary
