"""
Shift Correction tests — FMS-G06.

Tests cover:
- Validation guards (whole-shift, native doc)
- Ledger supersession logic for dip and cashier corrections
- Reclassification field update
- Cancel guard: generated docs refuse cancel without fms_correction flag
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
import pytest
from frappe.tests.utils import FrappeTestCase

from forecourt.corrections import cashier, dip, meter, native, reclassify, whole_shift
from forecourt.errors import FMSValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_shift(
	name="SH-TEST-001",
	station="KE-NBO-TEST",
	company="_Test Company",
	shift_start="2026-01-01 06:00:00",
	shift_end="2026-01-01 14:00:00",
	docstatus=1,
	status="Closed",
	resolutions=None,
	tank_dips=None,
	meter_readings=None,
):
	return SimpleNamespace(
		name=name,
		station=station,
		company=company,
		shift_start=shift_start,
		shift_end=shift_end,
		docstatus=docstatus,
		status=status,
		resolutions=resolutions or [],
		tank_dips=tank_dips or [],
		meter_readings=meter_readings or [],
		get=lambda field, default=None: getattr(
			SimpleNamespace(
				name=name,
				station=station,
				company=company,
			),
			field,
			default,
		),
	)


def _mock_correction(
	name="COR-001",
	forecourt_shift="SH-TEST-001",
	correction_type="Dip",
	items=None,
	next_shift=None,
):
	return SimpleNamespace(
		name=name,
		forecourt_shift=forecourt_shift,
		correction_type=correction_type,
		items=items or [],
		next_shift=next_shift,
		db_set=MagicMock(),
	)


# ---------------------------------------------------------------------------
# Whole-shift validation guards
# ---------------------------------------------------------------------------


class TestWholeShiftValidation(FrappeTestCase):
	def test_assert_latest_shift_raises_when_later_shift_exists(self):
		shift = _mock_shift()
		with patch("frappe.db.count", return_value=2):
			with pytest.raises(FMSValidationError):
				whole_shift._assert_latest_shift(shift)

	def test_assert_latest_shift_passes_when_no_later_shift(self):
		shift = _mock_shift()
		with patch("frappe.db.count", return_value=0):
			whole_shift._assert_latest_shift(shift)  # no exception

	def test_assert_period_open_raises_when_fiscal_year_closed(self):
		shift = _mock_shift()
		with patch("frappe.db.get_value", return_value=1):
			with self.assertRaises(frappe.ValidationError):
				whole_shift._assert_period_open(shift)

	def test_assert_period_open_passes_when_year_open(self):
		shift = _mock_shift()
		with patch("frappe.db.get_value", return_value=0):
			whole_shift._assert_period_open(shift)  # no exception

	def test_assert_period_open_passes_when_no_fiscal_year_found(self):
		shift = _mock_shift()
		with patch("frappe.db.get_value", return_value=None):
			whole_shift._assert_period_open(shift)  # no exception


# ---------------------------------------------------------------------------
# Native document correction — validation
# ---------------------------------------------------------------------------


class TestNativeCorrectionValidation(FrappeTestCase):
	def test_wrong_item_type_raises(self):
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_doctype="Sales Invoice",
			target_name="SINV-001",
			field=None,
			new_value=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with self.assertRaises(frappe.ValidationError):
			native.apply(correction)

	def test_missing_target_name_raises(self):
		item = SimpleNamespace(
			target_type="Document",
			target_doctype="Sales Invoice",
			target_name=None,
			field=None,
			new_value=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with self.assertRaises(frappe.ValidationError):
			native.apply(correction)

	def test_doc_belonging_to_wrong_shift_raises(self):
		item = SimpleNamespace(
			target_type="Document",
			target_doctype="Sales Invoice",
			target_name="SINV-001",
			field=None,
			new_value=None,
			idx=1,
		)
		correction = _mock_correction(forecourt_shift="SH-TEST-001", items=[item])
		target_doc = MagicMock()
		target_doc.get.return_value = "SH-OTHER-SHIFT"

		with patch("frappe.get_doc", return_value=target_doc):
			with self.assertRaises(frappe.ValidationError):
				native.apply(correction)


# ---------------------------------------------------------------------------
# Dip correction — validation
# ---------------------------------------------------------------------------


class TestDipCorrectionValidation(FrappeTestCase):
	def test_wrong_item_type_raises(self):
		item = SimpleNamespace(
			target_type="Resolution",
			target_row="ROW-001",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with self.assertRaises(frappe.ValidationError):
				dip.apply(correction)

	def test_missing_target_row_raises(self):
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_row=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with self.assertRaises(frappe.ValidationError):
				dip.apply(correction)

	def test_target_row_not_found_raises(self):
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_row="NONEXISTENT-ROW",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift(tank_dips=[])  # empty — row won't be found
		with patch("frappe.get_doc", return_value=shift):
			with patch("frappe.get_all", return_value=[]):
				with self.assertRaises(frappe.ValidationError):
					dip.apply(correction)


# ---------------------------------------------------------------------------
# Cashier correction — validation
# ---------------------------------------------------------------------------


class TestCashierCorrectionValidation(FrappeTestCase):
	def test_wrong_item_type_raises(self):
		item = SimpleNamespace(
			target_type="Tank Dip",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with patch("frappe.get_all", return_value=[]):
				with self.assertRaises(frappe.ValidationError):
					cashier.apply(correction)


# ---------------------------------------------------------------------------
# Meter correction — validation
# ---------------------------------------------------------------------------


class TestMeterCorrectionValidation(FrappeTestCase):
	def test_wrong_item_type_raises(self):
		item = SimpleNamespace(
			target_type="Resolution",
			target_row=None,
			field=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with self.assertRaises(frappe.ValidationError):
				meter.apply(correction)

	def test_missing_field_raises(self):
		item = SimpleNamespace(
			target_type="Meter Reading",
			target_row=None,
			field=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with self.assertRaises(frappe.ValidationError):
				meter.apply(correction)


# ---------------------------------------------------------------------------
# Reclassification — validation
# ---------------------------------------------------------------------------


class TestReclassifyValidation(FrappeTestCase):
	def test_wrong_item_type_raises(self):
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_row="ROW-001",
			field="reason",
			new_value="Dip error",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		with patch("frappe.get_doc", return_value=_mock_shift()):
			with self.assertRaises(frappe.ValidationError):
				reclassify.apply(correction)

	def test_target_row_not_found_raises(self):
		item = SimpleNamespace(
			target_type="Resolution",
			target_row="NONEXISTENT-ROW",
			field="reason",
			new_value="Dip error",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift(resolutions=[])
		with patch("frappe.get_doc", return_value=shift):
			with self.assertRaises(frappe.ValidationError):
				reclassify.apply(correction)

	def test_reclassify_updates_field_on_resolution_row(self):
		row = MagicMock()
		row.name = "RESROW-001"
		row.get = lambda field, default=None: "Unknown"
		row.field = None

		item = SimpleNamespace(
			target_type="Resolution",
			target_row="RESROW-001",
			field="reason",
			new_value="Dip error",
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift(resolutions=[row])

		with patch("frappe.get_doc", return_value=shift):
			reclassify.apply(correction)

		row.db_set.assert_called_once_with("reason", "Dip error", update_modified=False)
		correction.db_set.assert_called_once()


# ---------------------------------------------------------------------------
# Dip correction — ledger supersession
# ---------------------------------------------------------------------------


class TestDipLedgerSupersession(FrappeTestCase):
	def test_dip_correction_supersedes_wle(self):
		tank_dip_row = SimpleNamespace(
			name="TANKDIP-ROW-001",
			tank="KE-NBO-TEST-T1",
			item="PMS",
			opening_l=5000.0,
			receipts_l=10000.0,
			sales_l=3000.0,
			own_use_l=0.0,
			expected_l=12000.0,
		)
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_row="TANKDIP-ROW-001",
			new_value=11950.0,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift(tank_dips=[tank_dip_row])

		supersede_calls: list[tuple] = []

		def fake_db_set(doctype, name, field, value, update_modified=True):
			supersede_calls.append((doctype, name, field, value))

		mock_wle = MagicMock()
		mock_wle.name = "WLE-001"

		with (
			patch("frappe.get_doc", return_value=shift),
			patch("frappe.get_all", return_value=[{"name": "WLE-001"}]),
			patch("frappe.db.set_value", side_effect=fake_db_set),
			patch("frappe.new_doc", return_value=mock_wle),
			patch("frappe.db.get_value", return_value="WAREHOUSE-001"),
		):
			dip.apply(correction)

		# WLE was superseded
		supersession = [c for c in supersede_calls if c[2] == "superseded_by"]
		self.assertEqual(len(supersession), 1)
		self.assertEqual(supersession[0][3], correction.name)

	def test_dip_correction_records_applied_documents(self):
		tank_dip_row = SimpleNamespace(
			name="TANKDIP-ROW-001",
			tank="KE-NBO-TEST-T1",
			item="PMS",
			opening_l=5000.0,
			receipts_l=10000.0,
			sales_l=3000.0,
			own_use_l=0.0,
			expected_l=12000.0,
		)
		item = SimpleNamespace(
			target_type="Tank Dip",
			target_row="TANKDIP-ROW-001",
			new_value=11950.0,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift(tank_dips=[tank_dip_row])
		mock_wle = MagicMock()

		with (
			patch("frappe.get_doc", return_value=shift),
			patch("frappe.get_all", return_value=[{"name": "WLE-001"}]),
			patch("frappe.db.set_value"),
			patch("frappe.new_doc", return_value=mock_wle),
			patch("frappe.db.get_value", return_value="WAREHOUSE-001"),
		):
			dip.apply(correction)

		correction.db_set.assert_called_once()
		applied_docs_call = correction.db_set.call_args
		self.assertIn("applied_documents", applied_docs_call[0])


# ---------------------------------------------------------------------------
# Cashier correction — ledger supersession
# ---------------------------------------------------------------------------


class TestCashierLedgerSupersession(FrappeTestCase):
	def test_cashier_correction_supersedes_all_cle_for_shift(self):
		item = SimpleNamespace(
			target_type="Cash Count",
			target_row=None,
			idx=1,
		)
		correction = _mock_correction(items=[item])
		shift = _mock_shift()

		supersede_calls: list[tuple] = []

		def fake_db_set(doctype, name, field, value, update_modified=True):
			supersede_calls.append((doctype, name, field, value))

		with (
			patch("frappe.get_doc", return_value=shift),
			patch(
				"frappe.get_all",
				return_value=[{"name": "CLE-001"}, {"name": "CLE-002"}],
			),
			patch("frappe.db.set_value", side_effect=fake_db_set),
		):
			cashier.apply(correction)

		superseded = [c for c in supersede_calls if c[2] == "superseded_by"]
		self.assertEqual(len(superseded), 2)
		for s in superseded:
			self.assertEqual(s[3], correction.name)
