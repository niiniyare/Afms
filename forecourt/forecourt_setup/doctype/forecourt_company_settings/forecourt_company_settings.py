from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ForecourtCompanySettings(Document):
	pass


@frappe.whitelist()
def create_default_accounts(company: str) -> dict:
	"""Create missing FMS accounts and fill empty mappings for *company*.

	Takes only the company name: the unsaved form (and anything the browser autofilled
	into it, such as fiscal credentials) is never sent or saved by this action.
	"""
	from forecourt.setup.default_accounts import ensure_default_accounts

	frappe.has_permission("Forecourt Company Settings", "write", throw=True)
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} not found.").format(company))
	report = ensure_default_accounts(company)
	report["summary"] = _(
		"{0} account(s) created, {1} already existed; {2} mapping(s) set, {3} existing mapping(s) kept."
	).format(
		len(report["created"]),
		len(report["existing"]),
		len(report["mappings_set"]),
		len(report["mappings_kept"]),
	)
	return report
