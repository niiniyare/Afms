from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


def _company() -> str:
	return (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", limit=1, pluck="name")[0]
	)


def _expense_account(company: str) -> str:
	return frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Expense", "is_group": 0},
		"name",
	)


class TestOwnUsePurpose(FrappeTestCase):
	def setUp(self) -> None:
		self.company = _company()
		self.account = _expense_account(self.company)

	def tearDown(self) -> None:
		frappe.db.delete("Own Use Purpose", {"purpose": ["like", "_test_%"]})

	def test_insert(self) -> None:
		if not self.account:
			self.skipTest("No expense account on test site.")
		doc = frappe.get_doc(
			{
				"doctype": "Own Use Purpose",
				"purpose": "_test_Generator",
				"requires_vehicle": 0,
				"accounts": [{"company": self.company, "expense_account": self.account}],
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.name, "_test_Generator")
