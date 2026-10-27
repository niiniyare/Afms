"""F14: Post Stock Reconciliations and drop/float Payment Entries."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime


def post_stock_reconciliations(shift) -> list[str]:
	"""Post one Stock Reconciliation per tank with a closing dip.

	Respects Forecourt Company Settings.post_tank_variance:
	- 'Every shift with dips': post if a closing dip exists.
	- 'Outside tolerance only': post only when the variance exceeds the tolerance.
	- 'Last shift of day': same as 'Every shift with dips' (multi-shift detection not
	  yet implemented; treated as every shift for now — see FMS-F14 PR notes).

	Returns list of Stock Reconciliation names.
	"""
	company_settings = frappe.get_cached_doc("Forecourt Company Settings", shift.company)
	mode = (getattr(company_settings, "post_tank_variance", "") or "Every shift with dips").strip()
	posting_date = str(get_datetime(shift.shift_end).date())
	posting_time = get_datetime(shift.shift_end).strftime("%H:%M:%S")

	posted: list[str] = []

	for dip_row in shift.tank_dips:
		qty = flt(dip_row.dip_l, 3)
		if qty <= 0:
			continue

		if mode == "Outside tolerance only":
			if not _exceeds_tolerance(dip_row, company_settings):
				continue

		warehouse = frappe.db.get_value("Fuel Tank", dip_row.tank, "warehouse")
		if not warehouse:
			continue

		sr = frappe.new_doc("Stock Reconciliation")
		sr.company = shift.company
		sr.purpose = "Stock Reconciliation"
		sr.posting_date = posting_date
		sr.posting_time = posting_time
		sr.set_posting_time = 1
		sr.fms_forecourt_shift = shift.name
		sr.station = shift.station
		sr.append(
			"items",
			{
				"item_code": dip_row.item,
				"warehouse": warehouse,
				"qty": qty,
			},
		)
		sr.flags.ignore_permissions = True
		sr.insert(ignore_permissions=True)
		sr.submit()
		posted.append(sr.name)

	return posted


def post_drop_entries(shift) -> list[str]:
	"""Post one Internal Transfer Payment Entry per Drop collection (till → safe).

	Returns list of Payment Entry names.
	"""
	station = frappe.get_cached_doc("Station", shift.station)
	safe_account = getattr(station, "safe_account", None)
	if not safe_account:
		return []

	till_account = _till_account(station, shift.company)
	if not till_account:
		return []

	posting_date = str(get_datetime(shift.shift_end).date())
	posted: list[str] = []

	for row in shift.collections:
		if row.collection_type != "Drop":
			continue
		amount = flt(row.amount, 2)
		if amount <= 0:
			continue

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Internal Transfer"
		pe.company = shift.company
		pe.posting_date = posting_date
		pe.paid_from = till_account
		pe.paid_from_account_currency = frappe.db.get_value("Account", till_account, "account_currency")
		pe.paid_to = safe_account
		pe.paid_to_account_currency = frappe.db.get_value("Account", safe_account, "account_currency")
		pe.paid_amount = amount
		pe.received_amount = amount
		pe.fms_forecourt_shift = shift.name
		pe.fms_cashier = row.cashier
		pe.station = shift.station
		pe.flags.ignore_permissions = True
		pe.insert(ignore_permissions=True)
		pe.submit()
		posted.append(pe.name)
		frappe.db.set_value("Shift Collection", row.name, "payment_entry", pe.name, update_modified=False)

	return posted


def post_float_returns(shift) -> list[str]:
	"""Post Internal Transfer PEs returning cashier floats to the safe (D27).

	Only posted when Forecourt Company Settings.float_after_shift == 'Returned to safe'.
	Returns list of Payment Entry names.
	"""
	company_settings = frappe.get_cached_doc("Forecourt Company Settings", shift.company)
	if (getattr(company_settings, "float_after_shift", "") or "Stays in till") != "Returned to safe":
		return []

	station = frappe.get_cached_doc("Station", shift.station)
	safe_account = getattr(station, "safe_account", None)
	if not safe_account:
		return []

	till_account = _till_account(station, shift.company)
	if not till_account:
		return []

	posting_date = str(get_datetime(shift.shift_end).date())
	posted: list[str] = []

	for cashier_row in shift.cashiers:
		float_amount = flt(cashier_row.float_amount, 2)
		if float_amount <= 0:
			continue

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Internal Transfer"
		pe.company = shift.company
		pe.posting_date = posting_date
		pe.paid_from = till_account
		pe.paid_from_account_currency = frappe.db.get_value("Account", till_account, "account_currency")
		pe.paid_to = safe_account
		pe.paid_to_account_currency = frappe.db.get_value("Account", safe_account, "account_currency")
		pe.paid_amount = float_amount
		pe.received_amount = float_amount
		pe.fms_forecourt_shift = shift.name
		pe.fms_cashier = cashier_row.cashier
		pe.station = shift.station
		pe.flags.ignore_permissions = True
		pe.insert(ignore_permissions=True)
		pe.submit()
		posted.append(pe.name)

	return posted


# ── private helpers ──────────────────────────────────────────────────────────


def _till_account(station, company: str) -> str | None:
	company_currency = frappe.db.get_value("Company", company, "default_currency") or ""
	for row in station.till_accounts:
		if not row.currency or row.currency == company_currency:
			return row.account
	return station.till_accounts[0].account if station.till_accounts else None


def _exceeds_tolerance(dip_row, company_settings) -> bool:
	variance_l = flt(dip_row.variance_l, 3)
	variance_pct = flt(dip_row.variance_pct, 4)
	tol_l = flt(getattr(company_settings, "tank_tolerance_l", 20.0) or 20.0, 3)
	tol_pct = flt(getattr(company_settings, "tank_tolerance_pct", 0.5) or 0.5, 4) / 100.0
	return abs(variance_l) > tol_l or abs(variance_pct) > tol_pct
