import frappe
from frappe.tests.utils import FrappeTestCase

from forecourt.wetstock.doctype.nozzle.nozzle import Nozzle


class TestNozzle(FrappeTestCase):
	def _make_nozzle(self, **kwargs) -> Nozzle:
		defaults = {
			"doctype": "Nozzle",
			"dispenser": "TS-NBO-TSTL-TD01",
			"station": "TS-NBO-TSTL",
			"nozzle_no": 1,
			"tank": "TS-NBO-TSTL-TST1",
		}
		defaults.update(kwargs)
		return frappe.get_doc(defaults)

	def test_tank_wrong_station_raises(self):
		doc = self._make_nozzle()
		original = frappe.db.get_value

		def mock_get_value(dt, name, field, *args, **kwargs):
			if dt == "Fuel Tank" and name == "TS-NBO-TSTL-TST1" and field == "station":
				return "DIFFERENT-STATION"
			return original(dt, name, field, *args, **kwargs)

		frappe.db.get_value = mock_get_value
		try:
			self.assertRaisesRegex(frappe.ValidationError, "FMS-M606", doc._validate_tank_station)
		finally:
			frappe.db.get_value = original

	def test_tank_same_station_passes(self):
		doc = self._make_nozzle()
		original = frappe.db.get_value

		def mock_get_value(dt, name, field, *args, **kwargs):
			if dt == "Fuel Tank" and field == "station":
				return "TS-NBO-TSTL"
			return original(dt, name, field, *args, **kwargs)

		frappe.db.get_value = mock_get_value
		try:
			doc._validate_tank_station()
		finally:
			frappe.db.get_value = original

	def test_last_fields_skipped_for_new(self):
		doc = self._make_nozzle()
		doc._validate_last_fields()

	def test_last_fields_skipped_with_fms_flag(self):
		doc = self._make_nozzle()
		doc.flags.from_fms = True
		doc._validate_last_fields()
