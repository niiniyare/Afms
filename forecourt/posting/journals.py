"""F14: Post Journal Entries for expenses and cashier differences."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime


def post_expense_and_difference_je(shift) -> str:
	"""Post one Journal Entry per shift for expenses and cashier differences.

	Expense lines:      DR expense_account  CR till_account
	Shortage resolution: DR staff_shortage_receivable  CR till_account
	Excess resolution:  DR till_account  CR cash_over_account
	Write-off shortage: DR cash_short_account  CR till_account

	Returns the Journal Entry name, or empty string if there are no lines.
	"""
	company_settings = frappe.get_cached_doc("Forecourt Company Settings", shift.company)
	till_account = _till_account(shift)
	posting_date = str(get_datetime(shift.shift_end).date())
	posting_time = get_datetime(shift.shift_end).strftime("%H:%M:%S")

	accounts: list[dict] = []

	# Expense lines
	for row in shift.collections:
		if row.collection_type != "Expense":
			continue
		expense_account = _expense_account(row.expense_type, shift.company)
		if not expense_account or not flt(row.amount):
			continue
		amt = flt(row.amount, 2)
		accounts.append(
			{
				"account": expense_account,
				"debit_in_account_currency": amt,
				"cost_center": _company_cost_center(shift.company),
			}
		)
		accounts.append(
			{
				"account": till_account,
				"credit_in_account_currency": amt,
			}
		)

	# Resolution lines for cashier differences
	for row in shift.resolutions:
		if row.resolution_for != "Cashier":
			continue
		amt = flt(row.amount, 2)
		if amt <= 0:
			continue
		action = row.action
		cashier = row.cashier

		if action == "Charge to cashier":
			# DR staff_shortage_receivable (payable type), CR till
			shortage_acct = getattr(company_settings, "staff_shortage_receivable_account", None)
			if not shortage_acct:
				continue
			accounts.append(
				{
					"account": shortage_acct,
					"party_type": "Employee",
					"party": cashier,
					"debit_in_account_currency": amt,
				}
			)
			accounts.append(
				{
					"account": till_account,
					"credit_in_account_currency": amt,
				}
			)
		elif action == "Record excess":
			# DR till, CR cash_over_account (income)
			over_acct = getattr(company_settings, "cash_over_account", None)
			if not over_acct:
				continue
			accounts.append(
				{
					"account": till_account,
					"debit_in_account_currency": amt,
				}
			)
			accounts.append(
				{
					"account": over_acct,
					"credit_in_account_currency": amt,
				}
			)
		elif action == "Write off":
			# DR cash_short_account (expense), CR till
			short_acct = getattr(company_settings, "cash_short_account", None)
			if not short_acct:
				continue
			accounts.append(
				{
					"account": short_acct,
					"debit_in_account_currency": amt,
				}
			)
			accounts.append(
				{
					"account": till_account,
					"credit_in_account_currency": amt,
				}
			)

	if not accounts:
		return ""

	je = frappe.new_doc("Journal Entry")
	je.company = shift.company
	je.posting_date = posting_date
	je.posting_time = posting_time
	je.set_posting_time = 1
	je.fms_forecourt_shift = shift.name
	je.station = shift.station
	for acct in accounts:
		je.append("accounts", acct)
	je.flags.ignore_permissions = True
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


# ── private helpers ──────────────────────────────────────────────────────────


def _till_account(shift) -> str:
	station = frappe.get_cached_doc("Station", shift.station)
	company_currency = frappe.db.get_value("Company", shift.company, "default_currency") or ""
	for row in station.till_accounts:
		if not row.currency or row.currency == company_currency:
			return row.account
	return station.till_accounts[0].account if station.till_accounts else ""


def _expense_account(expense_type: str | None, company: str) -> str | None:
	if not expense_type:
		return None
	return frappe.db.get_value(
		"Expense Type Account",
		{"parent": expense_type, "company": company},
		"expense_account",
	)


def _company_cost_center(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "cost_center")
