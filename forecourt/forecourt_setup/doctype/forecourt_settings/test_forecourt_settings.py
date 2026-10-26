import frappe
from frappe.tests.utils import FrappeTestCase


def _settings(**kwargs):
	"""Return an unsaved ForecourtSettings doc with test values."""
	doc = frappe.get_doc(
		{
			"doctype": "Forecourt Settings",
			"record_ecash": 1,
			"record_evol": 0,
			"record_mvol": 0,
			"sales_basis": "E-cash",
			"accountable_person_label": "Cashier",
			"dip_entry_mode": "Depth via calibration chart",
			"drift_tolerance_pct": 0.5,
			"drift_tolerance_l": 2,
			"drift_requires_reason": 1,
			"price_change_mode": "Latest price with segments",
			"allow_time_estimated_segments": 0,
			"background_close_threshold": 200,
			"allow_backdated_shift_days": 2,
			"require_meter_photo": 0,
			"require_expense_receipt": 1,
		}
	)
	for k, v in kwargs.items():
		setattr(doc, k, v)
	return doc


class TestForecourtSettings(FrappeTestCase):
	def test_valid_ecash_default(self):
		_settings().validate()

	def test_valid_evol_with_evol_recorded(self):
		_settings(record_evol=1, sales_basis="E-vol").validate()

	def test_valid_mvol_with_mvol_recorded(self):
		_settings(record_mvol=1, sales_basis="M-vol").validate()

	def test_valid_highest_with_both_recorded(self):
		_settings(record_evol=1, sales_basis="Highest").validate()

	def test_evol_basis_without_evol_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_evol=0, sales_basis="E-vol").validate()

	def test_mvol_basis_without_mvol_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_mvol=0, sales_basis="M-vol").validate()

	def test_highest_without_evol(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_evol=0, sales_basis="Highest").validate()

	def test_highest_without_ecash(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_ecash=0, record_evol=1, sales_basis="Highest").validate()

	def test_no_meters_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			_settings(record_ecash=0, record_evol=0, record_mvol=0, sales_basis="E-cash").validate()

	def test_error_code_in_message(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"FMS-M603"):
			_settings(record_evol=0, sales_basis="E-vol").validate()
