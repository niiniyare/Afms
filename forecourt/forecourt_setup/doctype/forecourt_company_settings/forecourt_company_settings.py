from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ForecourtCompanySettings(Document):
	@frappe.whitelist()
	def create_default_accounts(self) -> dict[str, str]:
		from forecourt.setup.default_accounts import create_default_accounts

		accounts = create_default_accounts(self.company)
		frappe.msgprint(
			_("Created {0} accounts for {1}.").format(len(accounts), self.company),
			indicator="green",
		)
		return accounts
