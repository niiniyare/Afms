import frappe
from frappe.tests.utils import FrappeTestCase


class TestFuelTank(FrappeTestCase):
	def tearDown(self):
		frappe.db.delete("Fuel Tank", {"tank_code": ["like", "TST%"]})

	def _make_tank(self, **kwargs) -> frappe.Document:
		defaults = {
			"doctype": "Fuel Tank",
			"station": "TS-NBO-TSTL",
			"tank_code": "TST1",
			"item": frappe.db.get_value("Item", {"fms_is_fuel": 1}, "name") or "PMS",
			"capacity_l": 30000.0,
		}
		defaults.update(kwargs)
		return frappe.get_doc(defaults)

	def test_capacity_zero_raises(self):
		doc = self._make_tank(capacity_l=0)
		self.assertRaisesRegex(frappe.ValidationError, "FMS-M604", doc.validate)

	def test_capacity_negative_raises(self):
		doc = self._make_tank(capacity_l=-100)
		self.assertRaisesRegex(frappe.ValidationError, "FMS-M604", doc.validate)

	def test_safe_fill_exceeds_capacity_raises(self):
		doc = self._make_tank(capacity_l=10000, safe_fill_l=12000)
		self.assertRaisesRegex(frappe.ValidationError, "FMS-M604", doc.validate)

	def test_valid_tank_passes(self):
		doc = self._make_tank(capacity_l=30000, safe_fill_l=28500)
		doc.validate()

	def test_safe_fill_equal_capacity_passes(self):
		doc = self._make_tank(capacity_l=30000, safe_fill_l=30000)
		doc.validate()
