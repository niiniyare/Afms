"""Create FMS default accounts and modes of payment for a company.

Called from ForecourtCompanySettings.create_default_accounts() and from
the golden-scenario integration test.  Idempotent: existing records are
skipped.
"""

from __future__ import annotations

import frappe
from frappe import _


def create_default_accounts(company: str) -> dict[str, str]:
	"""Create the eleven FMS accounts, two Modes of Payment and link them in FCS.

	Returns a {slug: account_name} dict for all accounts. Use ensure_default_accounts()
	for the created / already-existing report.
	"""
	return ensure_default_accounts(company)["accounts"]


def ensure_default_accounts(company: str) -> dict:
	"""Idempotent setup that never overwrites existing records or mappings.

	Returns ``{"accounts", "created", "existing", "mappings_set", "mappings_kept",
	"clearing"}``. ``mappings_kept`` lists FCS fields that already pointed somewhere
	(left untouched); ``clearing`` reports each payment method's clearing account.
	"""
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		frappe.throw(_("Company {0} not found.").format(company))

	parents = _discover_parents(company)
	created: list[str] = []
	existing: list[str] = []
	accounts = _ensure_accounts(company, abbr, parents, created, existing)
	clearing = _ensure_modes_of_payment(company, accounts)
	mappings_set, mappings_kept = _update_fcs(company, accounts)
	return {
		"accounts": accounts,
		"created": created,
		"existing": existing,
		"mappings_set": mappings_set,
		"mappings_kept": mappings_kept,
		"clearing": clearing,
	}


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
	created: list[str],
	existing: list[str],
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
		(existing if frappe.db.exists("Account", full_name) else created).append(full_name)
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


def _ensure_modes_of_payment(company: str, accounts: dict[str, str]) -> list[dict]:
	return [
		_ensure_mop("Mobile Money", company, accounts["mobile_clearing"]),
		_ensure_mop("Card", company, accounts["card_clearing"]),
	]


def _ensure_mop(mop_name: str, company: str, account: str) -> dict:
	"""Make sure *mop_name* has a row for *company*; never replace an existing account."""
	if not frappe.db.exists("Mode of Payment", mop_name):
		mop = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mop_name, "type": "General"})
		mop.flags.ignore_permissions = True
		mop.insert()

	current = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mop_name, "company": company}, "default_account"
	)
	if current:
		acc = frappe.db.get_value("Account", current, ["company", "is_group"], as_dict=True)
		valid = bool(acc) and acc.company == company and not acc.is_group
		status = ("kept" if current == account else "kept (differs from default)") if valid else "invalid"
		return {"mode_of_payment": mop_name, "account": current, "default": account, "status": status}

	row_exists = frappe.db.exists("Mode of Payment Account", {"parent": mop_name, "company": company})
	mop = frappe.get_doc("Mode of Payment", mop_name)
	if row_exists:
		for row in mop.accounts:
			if row.company == company:
				row.default_account = account
	else:
		mop.append("accounts", {"company": company, "default_account": account})
	mop.flags.ignore_permissions = True
	mop.save()
	return {"mode_of_payment": mop_name, "account": account, "default": account, "status": "set"}


_FCS_FIELDS = (
	("staff_shortage_receivable_account", "staff_shortage"),
	("cash_short_account", "cash_short"),
	("cash_over_account", "cash_over"),
	("fuel_stock_variance_account", "fuel_variance"),
	("delivery_shortage_claims_account", "delivery_claims"),
	("voucher_clearing_account", "voucher_clearing"),
)


def _update_fcs(company: str, accounts: dict[str, str]) -> tuple[list[str], list[str]]:
	"""Fill empty FMS account links in Forecourt Company Settings; keep populated ones.

	Only the account fields are written; fiscal and other settings are never touched.
	"""
	if frappe.db.exists("Forecourt Company Settings", company):
		fcs = frappe.get_doc("Forecourt Company Settings", company)
	else:
		fcs = frappe.new_doc("Forecourt Company Settings")
		fcs.company = company

	mappings_set: list[str] = []
	mappings_kept: list[str] = []
	for field, slug in _FCS_FIELDS:
		if fcs.get(field):
			mappings_kept.append(field)
		else:
			fcs.set(field, accounts[slug])
			mappings_set.append(field)

	if mappings_set or fcs.is_new():
		fcs.flags.ignore_permissions = True
		fcs.flags.ignore_mandatory = True
		fcs.save()
	return mappings_set, mappings_kept
