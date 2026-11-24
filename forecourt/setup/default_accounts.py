"""Create FMS default accounts and modes of payment for a company.

Called from ForecourtCompanySettings.create_default_accounts() and from
the golden-scenario integration test.  Idempotent: existing records are
skipped.
"""

from __future__ import annotations

import frappe
from frappe import _


def create_default_accounts(company: str) -> dict[str, str]:
	"""Create the eleven FMS accounts, two Modes of Payment and update FCS.

	Returns a {slug: account_name} dict for all accounts.
	"""
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		frappe.throw(_("Company {0} not found.").format(company))

	parents = _discover_parents(company)
	accounts = _ensure_accounts(company, abbr, parents)
	_ensure_modes_of_payment(company, accounts)
	_update_fcs(company, accounts)
	return accounts


# ── private helpers ──────────────────────────────────────────────────────────


def _discover_parents(company: str) -> dict[str, str | None]:
	"""Return best-guess parent account names for each bucket."""

	def parent_of(filters: dict) -> str | None:
		return frappe.db.get_value(
			"Account",
			{**filters, "company": company, "is_group": 0},
			"parent_account",
		)

	def group_of(filters: dict) -> str | None:
		return frappe.db.get_value(
			"Account",
			{**filters, "company": company, "is_group": 1},
			"name",
		)

	cash_parent = parent_of({"account_type": "Cash"}) or group_of({"root_type": "Asset"})
	payable_parent = parent_of({"account_type": "Payable"}) or group_of({"root_type": "Liability"})
	expense_parent = parent_of({"account_type": "Expense Account"}) or group_of({"root_type": "Expense"})
	income_parent = parent_of({"account_type": "Income Account"}) or group_of({"root_type": "Income"})

	current_asset = (
		frappe.db.get_value(
			"Account",
			{
				"company": company,
				"root_type": "Asset",
				"is_group": 1,
				"account_name": ["like", "%Current%"],
			},
			"name",
		)
		or cash_parent
	)

	return {
		"cash": cash_parent,
		"payable": payable_parent,
		"expense": expense_parent,
		"income": income_parent,
		"current_asset": current_asset,
	}


def _ensure_accounts(
	company: str,
	abbr: str,
	parents: dict[str, str | None],
) -> dict[str, str]:
	"""Create the eleven FMS accounts if absent. Return slug → name dict."""

	# (slug, label, account_type, parent_key)
	specs = [
		("till", "FMS Cash in Till", "Cash", "cash"),
		("safe", "FMS Station Safe", "Cash", "cash"),
		("mobile_clearing", "FMS Mobile Money Clearing", "Bank", "current_asset"),
		("card_clearing", "FMS Card Clearing", "Bank", "current_asset"),
		("staff_shortage", "FMS Staff Shortage Payable", "Payable", "payable"),
		("cash_short", "FMS Cash Short", "Expense Account", "expense"),
		("cash_over", "FMS Cash Over", "Income Account", "income"),
		("fuel_variance", "FMS Fuel Stock Variance", "Expense Account", "expense"),
		("fuel_own_use", "FMS Fuel Own Use", "Expense Account", "expense"),
		("delivery_claims", "FMS Delivery Shortage Claims", "", "current_asset"),
		("voucher_clearing", "FMS Voucher Clearing", "", "current_asset"),
	]

	result: dict[str, str] = {}
	for slug, label, account_type, parent_key in specs:
		full_name = f"{label} - {abbr}"
		result[slug] = _ensure_account(full_name, label, company, account_type, parents.get(parent_key))
	return result


def _ensure_account(
	full_name: str,
	label: str,
	company: str,
	account_type: str,
	parent_account: str | None,
) -> str:
	"""Create account if absent; return its name."""
	if frappe.db.exists("Account", full_name):
		return full_name

	if not parent_account:
		frappe.throw(_("Cannot create {0}: no parent account found for {1}.").format(full_name, company))

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": label,
			"parent_account": parent_account,
			"company": company,
			"is_group": 0,
		}
	)
	if account_type:
		doc.account_type = account_type
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


def _ensure_modes_of_payment(company: str, accounts: dict[str, str]) -> None:
	_ensure_mop("Mobile Money", company, accounts["mobile_clearing"])
	_ensure_mop("Card", company, accounts["card_clearing"])


def _ensure_mop(mop_name: str, company: str, account: str) -> None:
	if not frappe.db.exists("Mode of Payment", mop_name):
		mop = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mop_name, "type": "General"})
		mop.flags.ignore_permissions = True
		mop.insert()

	existing_row = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mop_name, "company": company},
		"name",
	)
	if not existing_row:
		mop = frappe.get_doc("Mode of Payment", mop_name)
		mop.append("accounts", {"company": company, "default_account": account})
		mop.flags.ignore_permissions = True
		mop.save()


def _update_fcs(company: str, accounts: dict[str, str]) -> None:
	"""Create or update Forecourt Company Settings with FMS account links."""
	if frappe.db.exists("Forecourt Company Settings", company):
		fcs = frappe.get_doc("Forecourt Company Settings", company)
	else:
		fcs = frappe.new_doc("Forecourt Company Settings")
		fcs.company = company

	fcs.staff_shortage_receivable_account = accounts["staff_shortage"]
	fcs.cash_short_account = accounts["cash_short"]
	fcs.cash_over_account = accounts["cash_over"]
	fcs.fuel_stock_variance_account = accounts["fuel_variance"]
	fcs.delivery_shortage_claims_account = accounts["delivery_claims"]
	fcs.voucher_clearing_account = accounts["voucher_clearing"]

	fcs.flags.ignore_permissions = True
	fcs.flags.ignore_mandatory = True
	fcs.save()
