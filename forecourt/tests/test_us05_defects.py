"""Regression tests for US-05 UI verification defects.

BUG-02  _compute_credit_sale_rates falls back to shift_start when sold_at is empty.
BUG-03  _create_cashier_rows creates rows from template; _sync_cashier_rows fills gaps.
BUG-05  _compute_tank_dip_rows sets flag field server-side.
        _propagate_tank_resolution_reasons copies resolution reason to tank_dip.reason.
BUG-06  _find_previous_shift includes draft shifts.
        _gate_previous_shift_open adds an attention item when previous is a draft.
P3-1    Covered by JS; no Python test needed.
BUG-04  JE back-link in journals.py requires integration test (frappe.db); covered by
        test_shift_scenarios.py full-close assertions.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_MODULE = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift"

_TRANS_PATCHER = patch(f"{_MODULE}._", side_effect=lambda s, *a, **kw: s)
_FLT_PATCHER = patch(
	f"{_MODULE}.flt",
	side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
)
_GET_DT_PATCHER = patch(
	f"{_MODULE}.get_datetime",
	side_effect=lambda v: v,  # pass through for unit tests
)

_PATCHERS: list = []


def _make_db_mock():
	db = MagicMock()
	db.get_value.return_value = None
	db.exists.return_value = False
	db.set_value.return_value = None
	return db


def setUpModule():
	import frappe

	_PATCHERS[:] = [
		_TRANS_PATCHER,
		_FLT_PATCHER,
		_GET_DT_PATCHER,
		patch.object(frappe, "db", _make_db_mock()),
		patch.object(frappe, "get_all", MagicMock(return_value=[])),
		patch.object(frappe, "get_cached_doc", MagicMock()),
		patch.object(frappe, "throw", MagicMock(side_effect=Exception("frappe.throw"))),
	]
	for p in _PATCHERS:
		p.start()


def tearDownModule():
	for p in reversed(_PATCHERS):
		p.stop()
	_PATCHERS.clear()
	try:
		from frappe.tests.utils.generators import get_modules as _gm

		_gm.cache_clear()
	except (ImportError, AttributeError):
		pass


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
		"approval_state": "Not Required",
		"meter_readings": [],
		"tank_dips": [],
		"prices": [],
		"cashiers": [],
		"cash_counts": [],
		"credit_sales": [],
		"item_sales": [],
		"collections": [],
		"resolutions": [],
		"docstatus": 0,
	}
	defaults.update(kwargs)
	doc = SimpleNamespace(**defaults)

	# Add Frappe Document helpers that some methods rely on
	ForecourtShift = None

	def _get_segment_price(item, at_dt):
		nonlocal ForecourtShift
		if ForecourtShift is None:
			ForecourtShift = _import_shift()
		return ForecourtShift._get_segment_price(doc, item, at_dt)

	doc._get_segment_price = _get_segment_price

	def _append(table, row_dict):
		getattr(doc, table).append(SimpleNamespace(**row_dict))

	doc.append = _append

	return doc


def _row(**kwargs):
	return SimpleNamespace(**kwargs)


def _import_shift():
	from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

	return ForecourtShift


# ---------------------------------------------------------------------------
# BUG-02: credit sale rates fall back to shift_start when sold_at is empty
# ---------------------------------------------------------------------------


class TestCreditSaleRates(unittest.TestCase):
	"""BUG-02: _compute_credit_sale_rates uses shift_start when sold_at is empty."""

	def _run(self, credit_sales, prices, shift_start="2026-10-27 06:00:00"):
		ForecourtShift = _import_shift()
		doc = _make_shift(
			credit_sales=credit_sales,
			prices=prices,
			shift_start=shift_start,
		)
		ForecourtShift._compute_credit_sale_rates(doc)
		return doc.credit_sales

	def _price_row(self, item, price, eff_from=None, eff_to=None):
		return _row(item=item, price=price, effective_from=eff_from, effective_to=eff_to)

	def test_zero_sold_at_uses_shift_start_price(self):
		"""When sold_at is empty the shift_start price must be applied (BUG-02)."""
		sale = _row(item="PETROL", sold_at=None, qty=20.0, rate=0.0, amount=0.0)
		price = self._price_row("PETROL", 1.5)
		rows = self._run([sale], [price])
		self.assertAlmostEqual(rows[0].rate, 1.5)
		self.assertAlmostEqual(rows[0].amount, 30.0)

	def test_nonzero_sold_at_uses_segment_price(self):
		"""When sold_at is set the method still works correctly."""
		sale = _row(item="DIESEL", sold_at="2026-10-27 08:00:00", qty=10.0, rate=0.0, amount=0.0)
		price = self._price_row("DIESEL", 2.0)
		rows = self._run([sale], [price])
		self.assertAlmostEqual(rows[0].rate, 2.0)
		self.assertAlmostEqual(rows[0].amount, 20.0)

	def test_no_item_skipped(self):
		"""Row without item is skipped — no crash, no rate set."""
		sale = _row(item=None, sold_at=None, qty=5.0, rate=0.0, amount=0.0)
		rows = self._run([sale], [])
		self.assertEqual(rows[0].rate, 0.0)

	def test_no_matching_price_leaves_rate_zero(self):
		"""When no price segment matches, rate stays 0 (safe — gate will block submit)."""
		sale = _row(item="LPG", sold_at=None, qty=1.0, rate=0.0, amount=0.0)
		rows = self._run([sale], [])
		self.assertEqual(rows[0].rate, 0.0)


# ---------------------------------------------------------------------------
# BUG-03: cashier rows auto-synced
# ---------------------------------------------------------------------------


class TestSyncCashierRows(unittest.TestCase):
	"""BUG-03: _sync_cashier_rows adds missing cashier rows without duplicating."""

	def _run(self, cashiers, meter_readings=None, collections=None, credit_sales=None):
		ForecourtShift = _import_shift()
		doc = _make_shift(
			cashiers=cashiers,
			meter_readings=meter_readings or [],
			collections=collections or [],
			credit_sales=credit_sales or [],
		)
		# _sync_cashier_rows appends to doc.cashiers directly
		ForecourtShift._sync_cashier_rows(doc)
		return doc.cashiers

	def test_adds_missing_cashier_from_meter_readings(self):
		"""Cashier present in meter_readings but not cashiers table must be added (BUG-03)."""
		meter = [_row(cashier="EMP-001")]
		rows = self._run(cashiers=[], meter_readings=meter)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].cashier, "EMP-001")

	def test_no_duplicate_when_cashier_already_present(self):
		"""Cashier already in cashiers table must not be duplicated."""
		existing = [_row(cashier="EMP-001", float_amount=1000.0)]
		meter = [_row(cashier="EMP-001")]
		rows = self._run(cashiers=existing, meter_readings=meter)
		self.assertEqual(len(rows), 1)

	def test_adds_from_collections(self):
		col = [_row(cashier="EMP-002", collection_type="Mobile Money", amount=100)]
		rows = self._run(cashiers=[], collections=col)
		cashier_ids = [r.cashier for r in rows]
		self.assertIn("EMP-002", cashier_ids)

	def test_no_rows_added_when_no_references(self):
		rows = self._run(cashiers=[])
		self.assertEqual(rows, [])


# ---------------------------------------------------------------------------
# BUG-05: flag field set server-side + resolution reason propagated
# ---------------------------------------------------------------------------


class TestTankDipFlag(unittest.TestCase):
	"""BUG-05: _compute_tank_dip_rows sets flag; _propagate_tank_resolution_reasons copies reason."""

	def _run_dip_rows(self, tank_dips, meter_readings=None):
		ForecourtShift = _import_shift()
		doc = _make_shift(tank_dips=tank_dips, meter_readings=meter_readings or [])
		with (
			patch(
				f"{_MODULE}.calc_reconciliation.TankReconciliation",
				MagicMock(return_value=MagicMock()),
			),
			patch(
				f"{_MODULE}.calc_reconciliation.reconcile",
			),
			patch(
				f"{_MODULE}.calc_reconciliation.within_tolerance",
				return_value=True,
			),
		):
			ForecourtShift._compute_tank_dip_rows(doc)
		return doc.tank_dips

	def test_within_flag_set_when_in_tolerance(self):
		"""Flag must be 'Within' when dip_l > 0 and within_tolerance=1 (BUG-05)."""
		row = _row(
			tank="TK-01",
			dip_l=1000.0,
			opening_l=1100.0,
			receipts_l=0.0,
			sales_l=0.0,
			own_use_l=0.0,
			transfers_l=0.0,
			within_tolerance=0,
			needs_approval=0,
			flag="",
		)
		rows = self._run_dip_rows([row])
		# within_tolerance is set to 1 by the patched within_tolerance=True
		self.assertEqual(rows[0].flag, "Within")

	def test_empty_flag_when_no_dip(self):
		"""Flag must be empty string when dip_l is 0/None."""
		row = _row(
			tank="TK-01",
			dip_l=0.0,
			opening_l=1000.0,
			receipts_l=0.0,
			sales_l=0.0,
			own_use_l=0.0,
			transfers_l=0.0,
			within_tolerance=0,
			needs_approval=0,
			flag="",
		)
		rows = self._run_dip_rows([row])
		self.assertEqual(rows[0].flag, "")

	def test_approval_flag_set_when_outside_tolerance(self):
		"""Flag must be 'Approval' when needs_approval=1 (outside tolerance)."""
		ForecourtShift = _import_shift()
		doc = _make_shift(
			tank_dips=[
				_row(
					tank="TK-01",
					dip_l=800.0,
					opening_l=1100.0,
					receipts_l=0.0,
					sales_l=0.0,
					own_use_l=0.0,
					transfers_l=0.0,
					within_tolerance=0,
					needs_approval=0,
					flag="",
				)
			],
			meter_readings=[],
		)
		with (
			patch(f"{_MODULE}.calc_reconciliation.TankReconciliation", MagicMock(return_value=MagicMock())),
			patch(
				f"{_MODULE}.calc_reconciliation.reconcile",
			),
			patch(
				f"{_MODULE}.calc_reconciliation.within_tolerance",
				return_value=False,  # outside tolerance
			),
		):
			ForecourtShift._compute_tank_dip_rows(doc)
		self.assertEqual(doc.tank_dips[0].flag, "Approval")
		self.assertEqual(doc.tank_dips[0].needs_approval, 1)
		self.assertEqual(doc.tank_dips[0].within_tolerance, 0)

	def test_propagate_resolution_reason_to_tank_dip(self):
		"""Resolution reason must be copied to tank_dip.reason (BUG-05)."""
		ForecourtShift = _import_shift()
		tank_dip = _row(tank="TK-01", reason="", within_tolerance=0)
		resolution = _row(resolution_for="Tank", tank="TK-01", reason="Meter reading error")
		doc = _make_shift(tank_dips=[tank_dip], resolutions=[resolution])
		ForecourtShift._propagate_tank_resolution_reasons(doc)
		self.assertEqual(doc.tank_dips[0].reason, "Meter reading error")

	def test_no_propagation_when_resolution_has_no_reason(self):
		"""Resolution without reason must not overwrite an existing tank_dip reason."""
		ForecourtShift = _import_shift()
		tank_dip = _row(tank="TK-01", reason="Prior reason")
		resolution = _row(resolution_for="Tank", tank="TK-01", reason="")
		doc = _make_shift(tank_dips=[tank_dip], resolutions=[resolution])
		ForecourtShift._propagate_tank_resolution_reasons(doc)
		self.assertEqual(doc.tank_dips[0].reason, "Prior reason")

	def test_cashier_resolution_does_not_affect_tank_dip(self):
		"""Cashier resolution must not be copied to any tank_dip."""
		ForecourtShift = _import_shift()
		tank_dip = _row(tank="TK-01", reason="")
		resolution = _row(resolution_for="Cashier", tank=None, reason="Charge to cashier")
		doc = _make_shift(tank_dips=[tank_dip], resolutions=[resolution])
		ForecourtShift._propagate_tank_resolution_reasons(doc)
		self.assertEqual(doc.tank_dips[0].reason, "")


# ---------------------------------------------------------------------------
# BUG-06: _find_previous_shift uses submitted-only; readiness warns on draft previous
#
# PHASE-1 note: BUG-06 originally included drafts, but PHASE 1 reverted
# _find_previous_shift to docstatus=1 only.  The S116 before_insert gate
# prevents a draft-on-draft situation, so opening values always come from
# a verified submitted shift.  FMS-W104 covers the defensive edge case.
# ---------------------------------------------------------------------------


class TestFindPreviousShiftSubmittedOnly(unittest.TestCase):
	"""BUG-06 / PHASE-1: _find_previous_shift uses only docstatus=1 (submitted) shifts."""

	def test_submitted_only_in_query(self):
		"""get_all must be called with docstatus=1 (submitted only, PHASE-1 revert)."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001", previous_shift=None)

		frappe.get_all.return_value = [SimpleNamespace(name="SH-SUBMITTED-001")]
		ForecourtShift._find_previous_shift(doc)

		call_args = frappe.get_all.call_args
		self.assertIn("docstatus", str(call_args))
		# Must use 1, not [0, 1]
		self.assertIn("1", str(call_args))
		self.assertNotIn("[0, 1]", str(call_args))
		self.assertEqual(doc.previous_shift, "SH-SUBMITTED-001")

	def test_no_previous_shift_when_none_found(self):
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001", previous_shift="OLD-001")
		frappe.get_all.return_value = []
		ForecourtShift._find_previous_shift(doc)
		self.assertIsNone(doc.previous_shift)


class TestGatePreviousShiftOpen(unittest.TestCase):
	"""BUG-06: readiness gate warns (attention) when previous_shift is a draft."""

	def test_no_items_when_no_previous_shift(self):
		ForecourtShift = _import_shift()
		doc = _make_shift(previous_shift=None)
		items: list[dict] = []
		ForecourtShift._gate_previous_shift_open(doc, items)
		self.assertEqual(items, [])

	def test_no_items_when_previous_shift_submitted(self):
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(previous_shift="SH-001")
		frappe.db.get_value.return_value = 1  # docstatus 1 = submitted
		items: list[dict] = []
		ForecourtShift._gate_previous_shift_open(doc, items)
		self.assertEqual(items, [])

	def test_attention_item_when_previous_shift_is_draft(self):
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(previous_shift="SH-DRAFT-001")
		frappe.db.get_value.return_value = 0  # docstatus 0 = draft
		items: list[dict] = []
		ForecourtShift._gate_previous_shift_open(doc, items)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["severity"], "attention")
		self.assertEqual(items[0]["code"], "FMS-W104")


if __name__ == "__main__":
	unittest.main()
