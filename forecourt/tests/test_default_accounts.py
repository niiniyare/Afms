"""Create Default Accounts: idempotent, never overwrites mappings, reports counts."""

from __future__ import annotations

import frappe

from forecourt.forecourt_setup.doctype.forecourt_company_settings.forecourt_company_settings import (
	create_default_accounts as create_default_accounts_action,
)
from forecourt.setup.default_accounts import ensure_default_accounts
from forecourt.tests.factories import FMSTestCase


class TestDefaultAccounts(FMSTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.company = frappe.defaults.get_defaults().get("company") or "_Test Company"
		ensure_default_accounts(cls.company)

	def setUp(self) -> None:
		super().setUp()
		frappe.db.savepoint("fms_da")

	def tearDown(self) -> None:
		frappe.db.rollback(save_point="fms_da")
		super().tearDown()

	def test_second_run_creates_nothing_and_reports_existing(self) -> None:
		rep = ensure_default_accounts(self.company)
		self.assertEqual(rep["created"], [])
		self.assertEqual(len(rep["existing"]), 11)
		self.assertEqual(rep["mappings_set"], [])
		self.assertEqual(len(rep["mappings_kept"]), 6)

	def test_existing_mapping_is_preserved(self) -> None:
		other = frappe.db.get_value(
			"Account",
			{"company": self.company, "is_group": 0, "root_type": "Expense", "name": ["not like", "FMS%"]},
			"name",
		)
		self.assertTrue(other, "fixture needs a non-FMS expense account")
		frappe.db.set_value("Forecourt Company Settings", self.company, "cash_short_account", other)
		rep = ensure_default_accounts(self.company)
		self.assertEqual(
			frappe.db.get_value("Forecourt Company Settings", self.company, "cash_short_account"), other
		)
		self.assertIn("cash_short_account", rep["mappings_kept"])
		self.assertNotIn("cash_short_account", rep["mappings_set"])

	def test_empty_mapping_is_filled_and_reported(self) -> None:
		frappe.db.set_value("Forecourt Company Settings", self.company, "cash_over_account", None)
		rep = ensure_default_accounts(self.company)
		self.assertEqual(rep["mappings_set"], ["cash_over_account"])
		self.assertTrue(frappe.db.get_value("Forecourt Company Settings", self.company, "cash_over_account"))

	def test_fiscal_settings_untouched(self) -> None:
		frappe.db.set_value(
			"Forecourt Company Settings",
			self.company,
			{"fiscal_device_id": "BHF-7", "fiscal_api_url": "https://x.example"},
		)
		frappe.db.set_value("Forecourt Company Settings", self.company, "cash_over_account", None)
		ensure_default_accounts(self.company)
		vals = frappe.db.get_value(
			"Forecourt Company Settings", self.company, ["fiscal_device_id", "fiscal_api_url"], as_dict=True
		)
		self.assertEqual((vals.fiscal_device_id, vals.fiscal_api_url), ("BHF-7", "https://x.example"))

	def test_clearing_accounts_match_payment_methods(self) -> None:
		rep = ensure_default_accounts(self.company)
		by_mop = {c["mode_of_payment"]: c for c in rep["clearing"]}
		self.assertEqual(set(by_mop), {"Mobile Money", "Card"})
		for mop, c in by_mop.items():
			self.assertEqual(c["status"], "kept")
			stored = frappe.db.get_value(
				"Mode of Payment Account", {"parent": mop, "company": self.company}, "default_account"
			)
			self.assertEqual(stored, c["account"])
		self.assertIn("Mobile Money Clearing", by_mop["Mobile Money"]["account"])
		self.assertIn("Card Clearing", by_mop["Card"]["account"])

	def test_existing_clearing_account_not_replaced_but_flagged(self) -> None:
		other = frappe.db.get_value(
			"Account", {"company": self.company, "is_group": 0, "account_type": "Bank"}, "name"
		)
		if not other:
			self.skipTest("no alternative bank account in fixture")
		frappe.db.set_value(
			"Mode of Payment Account", {"parent": "Card", "company": self.company}, "default_account", other
		)
		rep = ensure_default_accounts(self.company)
		card = next(c for c in rep["clearing"] if c["mode_of_payment"] == "Card")
		self.assertEqual(card["account"], other)
		if other != card["default"]:
			self.assertEqual(card["status"], "kept (differs from default)")

	def test_action_reports_counts_and_ignores_form_payload(self) -> None:
		out = create_default_accounts_action(self.company)
		self.assertIn("0 account(s) created, 11 already existed", out["summary"])
		self.assertIn("6 existing mapping(s) kept", out["summary"])
