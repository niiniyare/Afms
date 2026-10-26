"""Unit tests for Forecourt Shift before_submit gates (FMS-F12).

Tests run without bench by patching frappe translation and DB calls.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_MODULE = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift"

# frappe._ and frappe.utils.flt both require site init. Patch them at the module level.
_TRANS_PATCHER = patch(f"{_MODULE}._", side_effect=lambda s, *a, **kw: s)
_FLT_PATCHER = patch(
	f"{_MODULE}.flt",
	side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
)


def setUpModule():
	import frappe

	_TRANS_PATCHER.start()
	_FLT_PATCHER.start()
	# frappe.db is an unbound LocalProxy without a site; replace with a mock.
	frappe.db = MagicMock()
	frappe.db.get_value.return_value = None
	frappe.db.exists.return_value = False
	frappe.db.count.return_value = 0


def tearDownModule():
	_FLT_PATCHER.stop()
	_TRANS_PATCHER.stop()


def _make_shift(**kwargs):
	defaults = {
		"name": "TEST-SHIFT-001",
		"station": "STA-001",
		"company": "Test Co",
		"shift_template": "Morning",
		"shift_date": "2026-10-27",
		"shift_start": "2026-10-27 06:00:00",
		"shift_end": "2026-10-27 14:00:00",
		"previous_shift": None,
		"meter_readings": [],
		"tank_dips": [],
		"prices": [],
		"cashiers": [],
		"cash_counts": [],
		"credit_sales": [],
		"item_sales": [],
		"collections": [],
		"resolutions": [],
	}
	defaults.update(kwargs)
	return SimpleNamespace(**defaults)


def _row(**kwargs):
	return SimpleNamespace(**kwargs)


def _import_shift():
	from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import (
		ForecourtShift,
	)

	return ForecourtShift


class TestGateNozzleReadings(unittest.TestCase):
	"""FMS-S101: closing >= opening or rollover ticked."""

	def _run(self, meter_readings):
		ForecourtShift = _import_shift()
		doc = _make_shift(meter_readings=meter_readings)
		errors: list[str] = []
		ForecourtShift._gate_nozzle_readings(doc, errors)
		return errors

	def test_ok_when_closing_above_opening(self):
		row = _row(
			nozzle="N1",
			rec_elec_cash=1,
			closing_elec_cash=1000.0,
			opening_elec_cash=900.0,
			rollover_elec_cash=0,
			rec_elec_meter=0,
			rec_man_meter=0,
		)
		self.assertEqual(self._run([row]), [])

	def test_fails_closing_below_opening_no_rollover(self):
		row = _row(
			nozzle="N1",
			rec_elec_cash=1,
			closing_elec_cash=100.0,
			opening_elec_cash=900.0,
			rollover_elec_cash=0,
			rec_elec_meter=0,
			rec_man_meter=0,
		)
		errors = self._run([row])
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S101", errors[0])

	def test_ok_when_rollover_ticked(self):
		row = _row(
			nozzle="N1",
			rec_elec_cash=1,
			closing_elec_cash=100.0,
			opening_elec_cash=900.0,
			rollover_elec_cash=1,
			rec_elec_meter=0,
			rec_man_meter=0,
		)
		self.assertEqual(self._run([row]), [])

	def test_fails_missing_closing_when_rec_enabled(self):
		row = _row(
			nozzle="N2",
			rec_elec_cash=1,
			closing_elec_cash=None,
			opening_elec_cash=500.0,
			rollover_elec_cash=0,
			rec_elec_meter=0,
			rec_man_meter=0,
		)
		errors = self._run([row])
		self.assertEqual(len(errors), 1)


class TestGateNozzleCashier(unittest.TestCase):
	"""FMS-S104: every nozzle reading must have a cashier."""

	def _run(self, meter_readings):
		ForecourtShift = _import_shift()
		doc = _make_shift(meter_readings=meter_readings)
		errors: list[str] = []
		ForecourtShift._gate_nozzle_cashier(doc, errors)
		return errors

	def test_ok_all_assigned(self):
		rows = [_row(nozzle="N1", cashier="EMP-001"), _row(nozzle="N2", cashier="EMP-002")]
		self.assertEqual(self._run(rows), [])

	def test_fails_missing_cashier(self):
		rows = [_row(nozzle="N1", cashier=None), _row(nozzle="N2", cashier="EMP-002")]
		errors = self._run(rows)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S104", errors[0])
		self.assertIn("N1", errors[0])


class TestGateCreditVolume(unittest.TestCase):
	"""FMS-S108: credit litres must not exceed metered litres."""

	def _run(self, credit_sales, meter_readings):
		ForecourtShift = _import_shift()
		doc = _make_shift(credit_sales=credit_sales, meter_readings=meter_readings)
		errors: list[str] = []
		ForecourtShift._gate_credit_volume(doc, errors)
		return errors

	def test_ok_credit_below_metered(self):
		credit = [_row(item="AGO", qty=100.0)]
		meters = [_row(item="AGO", net_volume_l=500.0)]
		self.assertEqual(self._run(credit, meters), [])

	def test_fails_credit_above_metered(self):
		credit = [_row(item="AGO", qty=600.0)]
		meters = [_row(item="AGO", net_volume_l=500.0)]
		errors = self._run(credit, meters)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S108", errors[0])

	def test_ok_exact_match(self):
		credit = [_row(item="PMS", qty=500.0)]
		meters = [_row(item="PMS", net_volume_l=500.0)]
		self.assertEqual(self._run(credit, meters), [])


class TestGateCashierResolved(unittest.TestCase):
	"""FMS-S105: every cashier difference must be resolved."""

	def _run(self, cashiers):
		ForecourtShift = _import_shift()
		doc = _make_shift(cashiers=cashiers)
		errors: list[str] = []
		ForecourtShift._gate_cashier_resolved(doc, errors)
		return errors

	def test_ok_all_resolved(self):
		rows = [
			_row(cashier="A", difference=0.0, resolved=1),
			_row(cashier="B", difference=50.0, resolved=1),
		]
		self.assertEqual(self._run(rows), [])

	def test_fails_unresolved_difference(self):
		rows = [_row(cashier="A", difference=-200.0, resolved=0)]
		errors = self._run(rows)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S105", errors[0])


class TestGateTestVolume(unittest.TestCase):
	"""FMS-S115: test volume must not exceed nozzle limit."""

	def _run_with_limit(self, meter_readings, limit):
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(meter_readings=meter_readings)
		errors: list[str] = []
		frappe.db.get_value.return_value = limit
		ForecourtShift._gate_test_volume(doc, errors)
		return errors

	def test_ok_within_limit(self):
		row = _row(nozzle="N1", test_volume_l=15.0)
		errors = self._run_with_limit([row], 20.0)
		self.assertEqual(errors, [])

	def test_fails_above_limit(self):
		row = _row(nozzle="N1", test_volume_l=25.0)
		errors = self._run_with_limit([row], 20.0)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S115", errors[0])

	def test_ok_no_limit_set(self):
		row = _row(nozzle="N1", test_volume_l=9999.0)
		errors = self._run_with_limit([row], 0.0)
		self.assertEqual(errors, [])


class TestMultipleGatesCollected(unittest.TestCase):
	"""Shift with two problems must list both codes in one throw."""

	def test_two_errors_collected(self):
		ForecourtShift = _import_shift()
		doc = _make_shift(
			meter_readings=[_row(nozzle="N1", cashier=None)],
			cashiers=[_row(cashier="EMP-001", difference=-100.0, resolved=0)],
		)
		errors: list[str] = []
		ForecourtShift._gate_nozzle_cashier(doc, errors)
		ForecourtShift._gate_cashier_resolved(doc, errors)
		self.assertEqual(len(errors), 2)
		codes = " ".join(errors)
		self.assertIn("FMS-S104", codes)
		self.assertIn("FMS-S105", codes)


if __name__ == "__main__":
	unittest.main()
