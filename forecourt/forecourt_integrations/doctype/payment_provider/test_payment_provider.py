from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPaymentProvider(FrappeTestCase):
	def tearDown(self) -> None:
		frappe.db.delete("Payment Provider", {"provider_name": ["like", "_test_%"]})

	def test_insert(self) -> None:
		mop = frappe.db.get_value("Mode of Payment", {}, "name")
		if not mop:
			self.skipTest("No Mode of Payment on test site.")
		doc = frappe.get_doc(
			{
				"doctype": "Payment Provider",
				"provider_name": "_test_Provider",
				"provider_type": "Mobile Money",
				"mode_of_payment": mop,
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.name, "_test_Provider")

	def test_unique_name(self) -> None:
		mop = frappe.db.get_value("Mode of Payment", {}, "name")
		if not mop:
			self.skipTest("No Mode of Payment on test site.")
		if not frappe.db.exists("Payment Provider", "_test_PP_dup"):
			frappe.get_doc(
				{
					"doctype": "Payment Provider",
					"provider_name": "_test_PP_dup",
					"provider_type": "Card",
					"mode_of_payment": mop,
				}
			).insert(ignore_permissions=True)
		with self.assertRaises(frappe.exceptions.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Payment Provider",
					"provider_name": "_test_PP_dup",
					"provider_type": "Bank",
					"mode_of_payment": mop,
				}
			).insert(ignore_permissions=True)
