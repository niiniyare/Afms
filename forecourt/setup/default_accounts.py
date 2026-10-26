"""Create the standard FMS accounts for a company and fill the mapping.

Called from Forecourt Company Settings.create_default_accounts().
Uses ignore_permissions because this runs as a privileged setup action.
"""

from __future__ import annotations

import frappe
from frappe import _

# (bare name, account_type, root_type, description)
_ACCOUNT_SPECS: list[tuple[str, str, str, str]] = [
	(
		"Staff Shortage Receivable",
		"Payable",
		"Liability",
		_("Cash shortages charged to cashiers"),
	),
	(
		"Cash Short",
		"Expense Account",
		"Expense",
		_("Written-off cash shortages"),
	),
	(
		"Cash Over",
		"Income Account",
		"Income",
		_("Written-off cash excesses"),
	),
	(
		"Fuel Stock Variance",
		"Expense Account",
		"Expense",
		_("Tank stock gains and losses"),
	),
	(
		"Delivery Shortage Claims",
		"Current Asset",
		"Asset",
		_("Delivery shortages claimed from suppliers or transporters"),
	),
	(
		"Voucher Clearing",
		"Current Asset",
		"Asset",
		_("Prepaid fuel vouchers redeemed at the station"),
	),
]

# Maps bare account name → Forecourt Company Settings fieldname
_FIELD_MAP: dict[str, str] = {
	"Staff Shortage Receivable": "staff_shortage_receivable_account",
	"Cash Short": "cash_short_account",
	"Cash Over": "cash_over_account",
	"Fuel Stock Variance": "fuel_stock_variance_account",
	"Delivery Shortage Claims": "delivery_shortage_claims_account",
	"Voucher Clearing": "voucher_clearing_account",
}


def create_default_accounts(settings_doc: "frappe.Document") -> None:
	"""Ensure all standard FMS accounts exist for the company and write mapping.

	Called with ignore_permissions in the whitelisted method so the action
	works for Forecourt Administrators who may lack Account create rights.
	"""
	company: str = settings_doc.company
	abbr: str = frappe.get_cached_value("Company", company, "abbr")
	created: list[str] = []
	existing: list[str] = []

	for bare_name, account_type, root_type, _description in _ACCOUNT_SPECS:
		full_name = f"{bare_name} - {abbr}"
		if not frappe.db.exists("Account", full_name):
			parent = _find_parent(company, root_type, account_type)
			account = frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": bare_name,
					"company": company,
					"parent_account": parent,
					"account_type": account_type,
					"root_type": root_type,
					"account_currency": frappe.get_cached_value("Company", company, "default_currency"),
				}
			)
			account.flags.ignore_permissions = True
			account.insert()
			created.append(full_name)
		else:
			existing.append(full_name)

		field = _FIELD_MAP.get(bare_name)
		if field and not settings_doc.get(field):
			settings_doc.set(field, full_name)

	if created:
		frappe.msgprint(
			_("Created accounts: {0}").format(", ".join(created)),
			title=_("Default Accounts Created"),
			indicator="green",
		)
	else:
		frappe.msgprint(
			_("All default accounts already exist."),
			title=_("No Accounts Created"),
			indicator="blue",
		)


def _find_parent(company: str, root_type: str, account_type: str) -> str:
	"""Return the most specific group account to park the new account under.

	Preference order:
	1. A group account matching both root_type and account_type
	2. Any group account matching root_type
	3. The root account of that type
	"""
	filters_specific = {
		"company": company,
		"root_type": root_type,
		"account_type": account_type,
		"is_group": 1,
	}
	parent = frappe.db.get_value("Account", filters_specific, "name", order_by="lft asc")
	if parent:
		return parent

	filters_root = {
		"company": company,
		"root_type": root_type,
		"is_group": 1,
	}
	parent = frappe.db.get_value("Account", filters_root, "name", order_by="lft asc")
	if parent:
		return parent

	# Last resort: the root account itself
	return frappe.db.get_value(
		"Account",
		{"company": company, "root_type": root_type, "parent_account": ["is", "not set"]},
		"name",
	)
