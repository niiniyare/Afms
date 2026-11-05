from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

_EXPECTED_DEFAULTS = [
	"Dip error",
	"Suspected leak",
	"Suspected theft",
	"Meter fault",
	"Temperature",
	"Delivery",
	"Counting error",
	"Drive-off (cashier)",
	"Spillage (tank)",
	"Unknown",
]


class TestVarianceReason(FrappeTestCase):
	def test_default_fixtures_exist(self) -> None:
		existing = frappe.get_all("Variance Reason", pluck="name")
		for name in _EXPECTED_DEFAULTS:
			self.assertIn(name, existing, f"Fixture record '{name}' missing")

	def test_insert_and_unique(self) -> None:
		if not frappe.db.exists("Variance Reason", "_test_VR_unique"):
			frappe.get_doc(
				{
					"doctype": "Variance Reason",
					"reason": "_test_VR_unique",
					"applies_to_tank": 1,
				}
			).insert(ignore_permissions=True)

		duplicate = frappe.get_doc({"doctype": "Variance Reason", "reason": "_test_VR_unique"})
		with self.assertRaises(frappe.exceptions.DuplicateEntryError):
			duplicate.insert(ignore_permissions=True)

	def tearDown(self) -> None:
		frappe.db.delete("Variance Reason", {"reason": "_test_VR_unique"})
