"""F13: Post Payment Entries for a closed Forecourt Shift."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime


def post_payment_entries(shift, walkin_invoice: str, credit_invoices: list[str]) -> list[str]:
	"""Post all Payment Entries for the shift.

	- One PE per Mobile Money collection (to provider clearing account).
	- One PE per Card collection (to provider clearing account).
	- One PE per Voucher collection (to voucher clearing account).
	- One cash PE per cashier (to till account).
	- One PE per Debt Receipt collection (from credit customer to till/clearing).

	All PEs carry fms_forecourt_shift, fms_cashier and the station dimension.
	Returns list of Payment Entry names.
	"""
	station = frappe.get_cached_doc("Station", shift.station)
	posting_date = str(get_datetime(shift.shift_end).date())
	company_settings = frappe.get_cached_doc("Forecourt Company Settings", shift.company)
	till_account = _till_account(station, shift.company)

	posted: list[str] = []

	for row in shift.collections:
		ct = row.collection_type
		if ct in ("Mobile Money", "Card"):
			pe_name = _make_provider_pe(shift, row, walkin_invoice, station, posting_date)
		elif ct == "Voucher":
			pe_name = _make_voucher_pe(shift, row, walkin_invoice, station, posting_date, company_settings)
		elif ct == "Debt Receipt":
			pe_name = _make_debt_receipt_pe(shift, row, station, posting_date, till_account)
		else:
			pe_name = ""

		if pe_name:
			posted.append(pe_name)
			frappe.db.set_value("Shift Collection", row.name, "payment_entry", pe_name, update_modified=False)

	# One cash PE per cashier
	if walkin_invoice:
		for cashier_row in shift.cashiers:
			cash_amount = flt(cashier_row.cash_counted, 2)
			if cash_amount <= 0:
				continue
			pe_name = _make_cash_pe(shift, cashier_row, walkin_invoice, station, posting_date, till_account)
			if pe_name:
				posted.append(pe_name)

	return posted


# ── private helpers ──────────────────────────────────────────────────────────


def _till_account(station, company: str) -> str | None:
	"""Return the base-currency till account for the station."""
	company_currency = frappe.db.get_value("Company", company, "default_currency") or ""
	for row in station.till_accounts:
		if not row.currency or row.currency == company_currency:
			return row.account
	return station.till_accounts[0].account if station.till_accounts else None


def _clearing_account(mode_of_payment: str, company: str) -> str | None:
	"""Return the clearing account for a Mode of Payment + Company."""
	return frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
		"default_account",
	)


def _receivable_account(customer: str, company: str) -> str:
	"""Return the receivable account for a customer."""
	from erpnext.accounts.party import get_party_account

	return get_party_account("Customer", customer, company)


def _base_pe(shift, posting_date: str) -> object:
	"""Return a new Payment Entry prefilled with shared fields."""
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = shift.company
	pe.posting_date = posting_date
	pe.fms_forecourt_shift = shift.name
	pe.station = shift.station
	return pe


def _allocate_to_invoice(pe, invoice_name: str, amount: float) -> None:
	"""Add a reference row to the walk-in invoice, capped at its outstanding amount."""
	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount") or 0, 2)
	allocated = min(flt(amount, 2), outstanding)
	if allocated > 0:
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": invoice_name,
				"outstanding_amount": outstanding,
				"allocated_amount": allocated,
			},
		)


def _submit_pe(pe) -> str:
	pe.flags.ignore_permissions = True
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def _make_provider_pe(shift, row, walkin_invoice: str, station, posting_date: str) -> str:
	"""One PE per Mobile Money or Card collection."""
	mop = row.mode_of_payment
	if not mop:
		return ""
	clearing = _clearing_account(mop, shift.company)
	if not clearing:
		return ""

	receivable = _receivable_account(station.walk_in_customer, shift.company)
	pe = _base_pe(shift, posting_date)
	pe.mode_of_payment = mop
	pe.party_type = "Customer"
	pe.party = station.walk_in_customer
	pe.paid_from = receivable
	pe.paid_from_account_currency = frappe.db.get_value("Account", receivable, "account_currency")
	pe.paid_to = clearing
	pe.paid_to_account_currency = frappe.db.get_value("Account", clearing, "account_currency")
	pe.paid_amount = flt(row.amount, 2)
	pe.received_amount = flt(row.amount, 2)
	pe.reference_no = row.reference or ""
	pe.reference_date = shift.shift_date
	pe.fms_cashier = row.cashier
	pe.fms_provider = row.provider
	pe.fms_till_or_terminal = row.till_or_terminal
	pe.fms_transaction_time = row.transaction_time

	if walkin_invoice:
		_allocate_to_invoice(pe, walkin_invoice, flt(row.amount, 2))

	return _submit_pe(pe)


def _make_voucher_pe(shift, row, walkin_invoice: str, station, posting_date: str, company_settings) -> str:
	"""One PE per Voucher collection — to voucher clearing account."""
	clearing = getattr(company_settings, "voucher_clearing_account", None)
	if not clearing:
		# Fall back to mode_of_payment clearing if configured
		if row.mode_of_payment:
			clearing = _clearing_account(row.mode_of_payment, shift.company)
	if not clearing:
		return ""

	receivable = _receivable_account(station.walk_in_customer, shift.company)
	pe = _base_pe(shift, posting_date)
	pe.mode_of_payment = row.mode_of_payment or ""
	pe.party_type = "Customer"
	pe.party = station.walk_in_customer
	pe.paid_from = receivable
	pe.paid_from_account_currency = frappe.db.get_value("Account", receivable, "account_currency")
	pe.paid_to = clearing
	pe.paid_to_account_currency = frappe.db.get_value("Account", clearing, "account_currency")
	pe.paid_amount = flt(row.amount, 2)
	pe.received_amount = flt(row.amount, 2)
	pe.reference_no = row.reference or ""
	pe.reference_date = shift.shift_date
	pe.fms_cashier = row.cashier

	if walkin_invoice:
		_allocate_to_invoice(pe, walkin_invoice, flt(row.amount, 2))

	return _submit_pe(pe)


def _make_debt_receipt_pe(shift, row, station, posting_date: str, till_account: str | None) -> str:
	"""One PE per Debt Receipt collection — from the credit customer."""
	if not row.customer:
		return ""

	paid_by = (row.paid_by or "Cash").strip()
	if paid_by in ("Mobile Money", "Card") and row.mode_of_payment:
		to_account = _clearing_account(row.mode_of_payment, shift.company)
	else:
		to_account = till_account
	if not to_account:
		return ""

	receivable = _receivable_account(row.customer, shift.company)
	pe = _base_pe(shift, posting_date)
	pe.mode_of_payment = row.mode_of_payment or ""
	pe.party_type = "Customer"
	pe.party = row.customer
	pe.paid_from = receivable
	pe.paid_from_account_currency = frappe.db.get_value("Account", receivable, "account_currency")
	pe.paid_to = to_account
	pe.paid_to_account_currency = frappe.db.get_value("Account", to_account, "account_currency")
	pe.paid_amount = flt(row.amount, 2)
	pe.received_amount = flt(row.amount, 2)
	pe.reference_no = row.reference or ""
	pe.reference_date = shift.shift_date
	pe.fms_cashier = row.cashier
	pe.fms_provider = row.provider
	pe.fms_till_or_terminal = row.till_or_terminal
	pe.fms_transaction_time = row.transaction_time

	return _submit_pe(pe)


def _make_cash_pe(
	shift, cashier_row, walkin_invoice: str, station, posting_date: str, till_account: str | None
) -> str:
	"""One cash PE per cashier — cash_counted into the till account."""
	if not till_account:
		return ""
	cash_amount = flt(cashier_row.cash_counted, 2)
	if cash_amount <= 0:
		return ""

	receivable = _receivable_account(station.walk_in_customer, shift.company)
	pe = _base_pe(shift, posting_date)
	pe.mode_of_payment = "Cash"
	pe.party_type = "Customer"
	pe.party = station.walk_in_customer
	pe.paid_from = receivable
	pe.paid_from_account_currency = frappe.db.get_value("Account", receivable, "account_currency")
	pe.paid_to = till_account
	pe.paid_to_account_currency = frappe.db.get_value("Account", till_account, "account_currency")
	pe.paid_amount = cash_amount
	pe.received_amount = cash_amount
	pe.reference_no = cashier_row.cashier or ""
	pe.reference_date = shift.shift_date
	pe.fms_cashier = cashier_row.cashier

	_allocate_to_invoice(pe, walkin_invoice, cash_amount)

	return _submit_pe(pe)
