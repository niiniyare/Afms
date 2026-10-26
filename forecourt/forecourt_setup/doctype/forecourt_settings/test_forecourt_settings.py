import frappe
from frappe.tests.utils import FrappeTestCase


def _settings(**kwargs):
	"""Return an unsaved ForecourtSettings doc with test values."""
	doc = frappe.get_doc(
		{
			"doctype": "Forecourt Settings",
			"record_elec_cash": 1,
			"record_elec_meter": 0,
			"record_man_meter": 0,
			"sales_basis": "Elec Cash",
			"accountable_person_label": "Cashier",
			"dip_entry_mode": "Depth via calibration chart",
			"drift_tolerance_pct": 0.5,
			"drift_tolerance_l": 2,
			"drift_requires_reason": 1,
			"price_change_mode": "Latest price with segments",
			"allow_estimated_segments": 0,
			"background_close_threshold": 200,
			"allow_backdated_shift_days": 2,
			"require_meter_reading_photo": 0,
			"require_expense_receipt": 1,
		}
	)
	for k, v in kwargs.items():
		setattr(doc, k, v)
	return doc


class TestForecourtSettings(FrappeTestCase):
	def test_valid_elec_cash_default(self):
		_settings().validate()

	def test_valid_elec_meter_with_elec_meter_recorded(self):
		_settings(record_elec_meter=1, sales_basis="Elec Meter").validate()

	def test_valid_man_meter_with_man_meter_recorded(self):
		_settings(record_man_meter=1, sales_basis="Man Meter").validate()

	def test_valid_highest_with_both_recorded(self):
		_settings(record_elec_meter=1, sales_basis="Highest").validate()

	def test_elec_meter_basis_without_elec_meter_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_elec_meter=0, sales_basis="Elec Meter").validate()

	def test_man_meter_basis_without_man_meter_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_man_meter=0, sales_basis="Man Meter").validate()

	def test_highest_without_elec_meter(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_elec_meter=0, sales_basis="Highest").validate()

	def test_highest_without_elec_cash(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_elec_cash=0, record_elec_meter=1, sales_basis="Highest").validate()

	def test_no_meters_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(
				record_elec_cash=0, record_elec_meter=0, record_man_meter=0, sales_basis="Elec Cash"
			).validate()

	def test_error_code_in_message(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"FMS-M603"):
			_settings(record_elec_meter=0, sales_basis="Elec Meter").validate()
