import frappe
from frappe.tests.utils import FrappeTestCase


class TestDispenser(FrappeTestCase):
	def _make_dispenser(self, **kwargs) -> frappe.Document:
		defaults = {
			"doctype": "Dispenser",
			"station": "TS-NBO-TSTL",
			"dispenser_code": "TD01",
			"meters_override": 0,
		}
		defaults.update(kwargs)
		return frappe.get_doc(defaults)

	def test_no_override_skips_meter_validation(self):
		doc = self._make_dispenser(meters_override=0)
		doc.validate()

	def test_override_no_meters_raises(self):
		doc = self._make_dispenser(
			meters_override=1,
			record_elec_cash=0,
			record_elec_meter=0,
			record_man_meter=0,
			sales_basis="Elec Cash",
		)
		self.assertRaisesRegex(frappe.ValidationError, "FMS-M603", doc.validate)

	def test_override_basis_requires_meter(self):
		doc = self._make_dispenser(
			meters_override=1,
			record_elec_cash=0,
			record_elec_meter=1,
			record_man_meter=0,
			sales_basis="Elec Cash",
		)
		self.assertRaisesRegex(frappe.ValidationError, "FMS-M603", doc.validate)

	def test_override_valid_passes(self):
		doc = self._make_dispenser(
			meters_override=1,
			record_elec_cash=1,
			record_elec_meter=0,
			record_man_meter=0,
			sales_basis="Elec Cash",
		)
		doc.validate()

	def test_override_highest_any_meter_passes(self):
		doc = self._make_dispenser(
			meters_override=1,
			record_elec_cash=1,
			record_elec_meter=1,
			record_man_meter=0,
			sales_basis="Highest",
		)
		doc.validate()
