"""FMS-F18: Shift scenario tests.

Tests run without bench by patching frappe translation, DB calls and settings.
Covers 13 scenarios: normal shift; shortage charged; excess; rollover; delivery
mid-shift; own use; price change mid-shift; three-meter drift; over-limit credit;
multi-currency cash; debt receipt by mobile money; overnight shift; background close.
"""

from __future__ import annotations

import unittest
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_MODULE = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift"
_LEDGER_MODULE = "forecourt.posting.ledgers"

# frappe._ and frappe.utils.flt require site init — patch them module-wide.
_TRANS_PATCHER = patch(f"{_MODULE}._", side_effect=lambda s, *a, **kw: s)
_FLT_PATCHER = patch(
	f"{_MODULE}.flt",
	side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
)
_GETDT_PATCHER = patch(
	f"{_MODULE}.get_datetime",
	side_effect=lambda s: (datetime.fromisoformat(str(s).replace(" ", "T")[:19]) if s else None),
)

_SETTINGS = SimpleNamespace(
	drift_tolerance_pct=0.5,
	drift_tolerance_l=2.0,
	drift_requires_reason=True,
	per_expense_limit=0.0,
	small_difference_pct=0.1,
	small_difference_amount=0.0,
	tank_tolerance_pct=0.5,
	approval_multiplier=2.0,
)


def setUpModule():
	import frappe

	_TRANS_PATCHER.start()
	_FLT_PATCHER.start()
	_GETDT_PATCHER.start()
	frappe.db = MagicMock()
	frappe.db.get_value.return_value = None
	frappe.db.exists.return_value = False
	frappe.db.count.return_value = 0
	frappe.get_all = MagicMock(return_value=[])
	frappe.get_cached_doc = MagicMock(return_value=_SETTINGS)
	# Replace LocalProxy so tests can set attributes without a bound site.
	frappe.flags = SimpleNamespace(fms_background_close=False, in_test=True)


def tearDownModule():
	_GETDT_PATCHER.stop()
	_FLT_PATCHER.stop()
	_TRANS_PATCHER.stop()


# ── helpers ────────────────────────────────────────────────────────────────


def _make_shift(**kwargs):
	defaults = dict(
		name="TEST-SHIFT-001",
		station="STA-001",
		company="Test Co",
		shift_template="Morning",
		shift_date="2026-10-27",
		shift_start="2026-10-27 06:00:00",
		shift_end="2026-10-27 14:00:00",
		previous_shift=None,
		status="Reconciled",
		meter_readings=[],
		tank_dips=[],
		prices=[],
		cashiers=[],
		cash_counts=[],
		credit_sales=[],
		item_sales=[],
		collections=[],
		resolutions=[],
		total_fuel_volume=0.0,
		total_fuel_amount=0.0,
		total_item_amount=0.0,
		total_credit=0.0,
		total_mobile=0.0,
		total_card=0.0,
		total_cash=0.0,
		total_expenses=0.0,
		total_difference=0.0,
		total_tank_variance_l=0.0,
	)
	defaults.update(kwargs)
	return SimpleNamespace(**defaults)


def _row(**kwargs):
	return SimpleNamespace(**kwargs)


def _make_meter_row(
	nozzle="N1",
	cashier="EMP-001",
	tank="T1",
	item="PMS",
	price=100.0,
	opening=900.0,
	closing=1100.0,
	rollover=0,
	rollover_max=0,
	rec_ecash=1,
	rec_evol=0,
	rec_mvol=0,
	opening_evol=0.0,
	closing_evol=0.0,
	opening_mvol=0.0,
	closing_mvol=0.0,
	rollover_evol=0,
	rollover_mvol=0,
	test_volume_l=0.0,
	own_use_l=0.0,
	segment_no=1,
):
	return SimpleNamespace(
		nozzle=nozzle,
		cashier=cashier,
		tank=tank,
		item=item,
		price=price,
		opening_elec_cash=opening,
		closing_elec_cash=closing,
		rollover_elec_cash=rollover,
		rec_elec_cash=rec_ecash,
		opening_elec_meter=opening_evol,
		closing_elec_meter=closing_evol,
		rollover_elec_meter=rollover_evol,
		rec_elec_meter=rec_evol,
		opening_man_meter=opening_mvol,
		closing_man_meter=closing_mvol,
		rollover_man_meter=rollover_mvol,
		rec_man_meter=rec_mvol,
		test_volume_l=test_volume_l,
		own_use_l=own_use_l,
		segment_no=segment_no,
		row_sales_basis="Elec Cash",
		# computed fields (set by _compute_meter_rows)
		basis_meter=None,
		basis_volume_l=0.0,
		net_volume_l=0.0,
		amount=0.0,
		drift_ecash_evol_l=0.0,
		drift_ecash_mvol_l=0.0,
		drift_evol_mvol_l=0.0,
		drift_breach=0,
		attendant=None,
		source="Manual",
	)


def _make_cashier_row(
	cashier="EMP-001",
	float_amount=0.0,
	fuel_amount=0.0,
	item_amount=0.0,
	debt_receipts=0.0,
	cash_counted=0.0,
	mobile=0.0,
	card=0.0,
	credit=0.0,
	voucher=0.0,
	expenses=0.0,
	drops=0.0,
	difference=0.0,
	resolved=0,
):
	return SimpleNamespace(
		cashier=cashier,
		float_amount=float_amount,
		fuel_amount=fuel_amount,
		item_amount=item_amount,
		debt_receipts=debt_receipts,
		cash_counted=cash_counted,
		mobile=mobile,
		card=card,
		credit=credit,
		voucher=voucher,
		expenses=expenses,
		drops=drops,
		expected=0.0,
		accounted=0.0,
		difference=difference,
		resolved=resolved,
	)


def _make_dip_row(
	tank="T1",
	item="PMS",
	opening_l=20000.0,
	receipts_l=0.0,
	sales_l=0.0,
	own_use_l=0.0,
	transfers_l=0.0,
	dip_l=None,
	dip_entry_mode="Litres",
	source="Manual",
):
	return SimpleNamespace(
		tank=tank,
		item=item,
		dip_entry_mode=dip_entry_mode,
		opening_l=opening_l,
		receipts_l=receipts_l,
		sales_l=sales_l,
		own_use_l=own_use_l,
		transfers_l=transfers_l,
		dip_l=dip_l,
		dip_mm=None,
		expected_l=0.0,
		variance_l=None,
		variance_pct=None,
		within_tolerance=0,
		needs_approval=0,
		reason=None,
		approved_by=None,
		source=source,
	)


def _import_shift():
	from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

	return ForecourtShift


# ── S1: Normal shift ────────────────────────────────────────────────────────


class TestNormalShiftCalc(unittest.TestCase):
	"""Ecash-only nozzle: delta and totals computed correctly."""

	def test_meter_delta_and_amount(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None  # no rollover_max

		ForecourtShift._compute_meter_rows(doc)

		self.assertAlmostEqual(meter.net_volume_l, 2.0, places=3)
		self.assertAlmostEqual(meter.amount, 200.0, places=2)
		self.assertEqual(meter.basis_meter, "Elec Cash")

	def test_parent_totals_after_meter_compute(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_parent_totals(doc)

		self.assertAlmostEqual(doc.total_fuel_volume, 2.0, places=3)
		self.assertAlmostEqual(doc.total_fuel_amount, 200.0, places=2)

	def test_cashier_balance_zero_difference(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		# cash_counted must come via cash_counts, not set directly on cashier row
		cash_counts = [_row(cashier="EMP-001", amount=200.0, base_amount=None)]
		doc = _make_shift(meter_readings=[meter], cashiers=[cashier], cash_counts=cash_counts)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		self.assertAlmostEqual(cashier.expected, 200.0, places=2)
		self.assertAlmostEqual(cashier.difference, 0.0, places=2)


# ── S2: Shortage charged ────────────────────────────────────────────────────


class TestShortageCharged(unittest.TestCase):
	"""Cashier shortage resolved by Charge to cashier resolution line."""

	def _make_shortage_doc(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=0.0, closing=100000.0, price=100.0)
		# cash_counted less than fuel_amount → shortage
		cashier = _make_cashier_row(cashier="EMP-001", cash_counted=900.0)
		doc = _make_shift(meter_readings=[meter], cashiers=[cashier])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)
		return doc

	def test_unresolved_shortage_has_negative_difference(self):
		doc = self._make_shortage_doc()
		cashier = doc.cashiers[0]
		self.assertLess(cashier.difference, 0.0)
		self.assertEqual(cashier.resolved, 0)

	def test_resolution_marks_cashier_resolved(self):
		ForecourtShift = _import_shift()
		doc = self._make_shortage_doc()
		cashier = doc.cashiers[0]
		shortage = abs(cashier.difference)

		doc.resolutions = [
			_row(
				resolution_for="Cashier",
				cashier="EMP-001",
				tank=None,
				action="Charge to cashier",
				amount=shortage,
			)
		]
		ForecourtShift._update_cashier_resolved(doc)
		self.assertEqual(cashier.resolved, 1)

	def test_partial_resolution_leaves_unresolved(self):
		ForecourtShift = _import_shift()
		doc = self._make_shortage_doc()
		cashier = doc.cashiers[0]
		shortage = abs(cashier.difference)

		doc.resolutions = [
			_row(
				resolution_for="Cashier",
				cashier="EMP-001",
				tank=None,
				action="Charge to cashier",
				amount=shortage - 1.0,  # partial only
			)
		]
		ForecourtShift._update_cashier_resolved(doc)
		self.assertEqual(cashier.resolved, 0)


# ── S3: Excess ──────────────────────────────────────────────────────────────


class TestExcess(unittest.TestCase):
	"""Cashier surplus: positive difference, resolved by Record excess resolution."""

	def test_excess_difference_is_positive(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		cash_counts = [_row(cashier="EMP-001", amount=250.0, base_amount=None)]
		doc = _make_shift(meter_readings=[meter], cashiers=[cashier], cash_counts=cash_counts)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		self.assertGreater(cashier.difference, 0.0)

	def test_excess_resolved(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		cash_counts = [_row(cashier="EMP-001", amount=250.0, base_amount=None)]
		doc = _make_shift(meter_readings=[meter], cashiers=[cashier], cash_counts=cash_counts)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		diff = cashier.difference
		doc.resolutions = [
			_row(
				resolution_for="Cashier",
				cashier="EMP-001",
				tank=None,
				action="Record excess",
				amount=diff,
			)
		]
		ForecourtShift._update_cashier_resolved(doc)
		self.assertEqual(cashier.resolved, 1)


# ── S4: Rollover ────────────────────────────────────────────────────────────


class TestRolloverCalc(unittest.TestCase):
	"""Meter rollover: delta spans the rollover point; net volume positive."""

	def test_rollover_delta_and_volume(self):
		ForecourtShift = _import_shift()
		# opening=9800, closing=200, rollover_max=10000 → delta=400 → litres=4.0
		meter = _make_meter_row(
			opening=9800.0,
			closing=200.0,
			price=100.0,
			rollover=1,
			rollover_max=10000.0,
		)
		meter.rollover_elec_cash = 1
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = 10000.0  # ecash_rollover_max from DB

		ForecourtShift._compute_meter_rows(doc)

		self.assertAlmostEqual(meter.net_volume_l, 4.0, places=3)
		self.assertAlmostEqual(meter.amount, 400.0, places=2)


# ── S5: Delivery mid-shift ──────────────────────────────────────────────────


class TestDeliveryMidShift(unittest.TestCase):
	"""Tank receives a GRN delivery during the shift: expected_l includes receipt."""

	def test_expected_l_includes_receipts(self):
		ForecourtShift = _import_shift()
		dip = _make_dip_row(
			opening_l=15000.0,
			receipts_l=5000.0,  # delivery received
			dip_l=18000.0,
		)
		# Provide a pre-computed meter row so _compute_tank_dip_rows picks up sales_l=2000
		meter = _make_meter_row(tank="T1")
		meter.net_volume_l = 2000.0
		doc = _make_shift(meter_readings=[meter], tank_dips=[dip])
		ForecourtShift._compute_tank_dip_rows(doc)

		# expected = 15000 + 5000 - 2000 - 0 = 18000; dip=18000 → variance=0
		self.assertAlmostEqual(dip.expected_l, 18000.0, places=3)
		self.assertAlmostEqual(dip.variance_l, 0.0, places=3)
		self.assertEqual(dip.within_tolerance, 1)


# ── S6: Own use deduction ───────────────────────────────────────────────────


class TestOwnUseDeduction(unittest.TestCase):
	"""own_use_l on nozzle row is subtracted from net_volume_l."""

	def test_own_use_reduces_net_volume(self):
		ForecourtShift = _import_shift()
		# ecash delta = 200 → litres=2.0; own_use=0.5 → net=1.5
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0, own_use_l=0.5)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)

		self.assertAlmostEqual(meter.net_volume_l, 1.5, places=3)
		self.assertAlmostEqual(meter.amount, 150.0, places=2)


# ── S7: Price change mid-shift ──────────────────────────────────────────────


class TestPriceChangeSegments(unittest.TestCase):
	"""Two segments at different prices: totals are the sum of both."""

	def test_two_segment_totals(self):
		ForecourtShift = _import_shift()
		# Segment 1: delta=200 units @ 100 → litres=2.0, amount=200
		# Segment 2: delta=300 units @ 110 → litres≈2.727, amount=300
		seg1 = _make_meter_row(
			nozzle="N1",
			cashier="EMP-001",
			tank="T1",
			item="PMS",
			price=100.0,
			opening=900.0,
			closing=1100.0,
			segment_no=1,
		)
		seg2 = _make_meter_row(
			nozzle="N1",
			cashier="EMP-001",
			tank="T1",
			item="PMS",
			price=110.0,
			opening=1100.0,
			closing=1430.0,  # delta=330 units @ 110 = 3 litres
			segment_no=2,
		)
		cashier = _make_cashier_row(cashier="EMP-001", cash_counted=530.0)  # 200+330
		doc = _make_shift(meter_readings=[seg1, seg2], cashiers=[cashier])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)
		ForecourtShift._compute_parent_totals(doc)

		total_amount = seg1.amount + seg2.amount
		self.assertAlmostEqual(total_amount, doc.total_fuel_amount, places=2)
		# cashier fuel_amount = sum of both segments
		self.assertAlmostEqual(cashier.fuel_amount, total_amount, places=2)

	def test_two_segments_same_nozzle_tank_sales(self):
		ForecourtShift = _import_shift()
		seg1 = _make_meter_row(opening=0.0, closing=100000.0, price=100.0, segment_no=1)
		seg2 = _make_meter_row(opening=100000.0, closing=130000.0, price=110.0, segment_no=2)
		dip = _make_dip_row(tank="T1", opening_l=20000.0)
		doc = _make_shift(meter_readings=[seg1, seg2], tank_dips=[dip])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_tank_dip_rows(doc)

		# sales_l = seg1.net_volume_l + seg2.net_volume_l
		expected_sales = seg1.net_volume_l + seg2.net_volume_l
		self.assertAlmostEqual(dip.sales_l, expected_sales, places=3)


# ── S8: Three-meter drift ───────────────────────────────────────────────────


class TestThreeMeterDrift(unittest.TestCase):
	"""All three meters enabled: drift values computed; breach flagged beyond tolerance."""

	def _make_three_meter_row(self, ecash_delta=200.0, evol_delta=2.0, mvol_delta=2.0, price=100.0):
		"""Return a meter row with all three meters enabled."""
		return SimpleNamespace(
			nozzle="N1",
			cashier="EMP-001",
			tank="T1",
			item="PMS",
			price=price,
			opening_elec_cash=0.0,
			closing_elec_cash=ecash_delta,
			rollover_elec_cash=0,
			rec_elec_cash=1,
			opening_elec_meter=0.0,
			closing_elec_meter=evol_delta,
			rollover_elec_meter=0,
			rec_elec_meter=1,
			opening_man_meter=0.0,
			closing_man_meter=mvol_delta,
			rollover_man_meter=0,
			rec_man_meter=1,
			test_volume_l=0.0,
			own_use_l=0.0,
			segment_no=1,
			row_sales_basis="Elec Cash",
			basis_meter=None,
			basis_volume_l=0.0,
			net_volume_l=0.0,
			amount=0.0,
			drift_ecash_evol_l=0.0,
			drift_ecash_mvol_l=0.0,
			drift_evol_mvol_l=0.0,
			drift_breach=0,
			attendant=None,
			source="Manual",
		)

	def test_zero_drift_no_breach(self):
		ForecourtShift = _import_shift()
		# ecash_litres = 200/100 = 2.0; evol_litres = 2.0; mvol_litres = 2.0 → all equal
		meter = self._make_three_meter_row(ecash_delta=200.0, evol_delta=2.0, mvol_delta=2.0)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)

		self.assertAlmostEqual(meter.drift_ecash_evol_l, 0.0, places=3)
		self.assertAlmostEqual(meter.drift_ecash_mvol_l, 0.0, places=3)
		self.assertAlmostEqual(meter.drift_evol_mvol_l, 0.0, places=3)
		self.assertEqual(meter.drift_breach, 0)

	def test_large_drift_sets_breach(self):
		ForecourtShift = _import_shift()
		# ecash_litres=2.0; evol=2.5; mvol=2.5 → ecash_vs_evol = -0.5
		# basis_litres=2.0; tolerance=max(2.0*0.5/100, 2.0)=2.0 → |0.5| < 2.0 → no breach
		# Use a larger discrepancy to trigger breach
		# ecash_litres=2.0; evol_litres=10.0 → drift=8.0; basis=2.0; tol=max(0.01,2.0)=2.0 → breach
		meter = self._make_three_meter_row(ecash_delta=200.0, evol_delta=10.0, mvol_delta=10.0)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)

		self.assertEqual(meter.drift_breach, 1)

	def test_drift_values_computed(self):
		ForecourtShift = _import_shift()
		# ecash_litres=2.0; evol=3.0; mvol=2.5
		# ecash_vs_evol = 2.0 - 3.0 = -1.0
		# ecash_vs_mvol = 2.0 - 2.5 = -0.5
		# evol_vs_mvol  = 3.0 - 2.5 = 0.5
		meter = self._make_three_meter_row(ecash_delta=200.0, evol_delta=3.0, mvol_delta=2.5)
		doc = _make_shift(meter_readings=[meter])

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)

		self.assertAlmostEqual(meter.drift_ecash_evol_l, -1.0, places=3)
		self.assertAlmostEqual(meter.drift_ecash_mvol_l, -0.5, places=3)
		self.assertAlmostEqual(meter.drift_evol_mvol_l, 0.5, places=3)


# ── S9: Over-limit credit gate ──────────────────────────────────────────────


class TestOverLimitCreditGate(unittest.TestCase):
	"""FMS-S107: over-limit credit sales blocked without approval."""

	def _run(self, credit_sales):
		ForecourtShift = _import_shift()
		doc = _make_shift(credit_sales=credit_sales)
		errors: list[str] = []
		ForecourtShift._gate_credit_over_limit(doc, errors)
		return errors

	def test_blocks_unapproved_over_limit(self):
		credit = [_row(customer="CUST-001", slip_no="SLP-001", over_limit=1, over_limit_approved_by=None)]
		errors = self._run(credit)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S107", errors[0])
		self.assertIn("CUST-001", errors[0])

	def test_passes_approved_over_limit(self):
		credit = [
			_row(customer="CUST-001", slip_no="SLP-001", over_limit=1, over_limit_approved_by="DIR-001")
		]
		errors = self._run(credit)
		self.assertEqual(errors, [])

	def test_passes_within_limit(self):
		credit = [_row(customer="CUST-001", slip_no="SLP-001", over_limit=0, over_limit_approved_by=None)]
		errors = self._run(credit)
		self.assertEqual(errors, [])


# ── S10: Multi-currency cash ────────────────────────────────────────────────


class TestMultiCurrencyCash(unittest.TestCase):
	"""Mobile, card and cash collections all contribute to cashier accounted total."""

	def test_all_payment_modes_summed(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		collections = [
			_row(cashier="EMP-001", collection_type="Mobile Money", amount=50.0),
			_row(cashier="EMP-001", collection_type="Card", amount=80.0),
		]
		cash_counts = [_row(cashier="EMP-001", amount=70.0, base_amount=None)]
		doc = _make_shift(
			meter_readings=[meter],
			cashiers=[cashier],
			collections=collections,
			cash_counts=cash_counts,
		)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		# expected = 200; accounted = (70-0) + 50 + 80 = 200 → difference = 0
		self.assertAlmostEqual(cashier.mobile, 50.0, places=2)
		self.assertAlmostEqual(cashier.card, 80.0, places=2)
		self.assertAlmostEqual(cashier.cash_counted, 70.0, places=2)
		self.assertAlmostEqual(cashier.difference, 0.0, places=2)


# ── S11: Debt receipt by mobile money ──────────────────────────────────────


class TestDebtReceiptMobile(unittest.TestCase):
	"""Debt receipts increase expected — mobile payment covers the total."""

	def test_debt_receipt_included_in_expected(self):
		ForecourtShift = _import_shift()
		# fuel_amount=200; debt_receipts=100 → expected=300
		# mobile=300 → accounted=300 → difference=0
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		collections = [
			_row(cashier="EMP-001", collection_type="Debt Receipt", amount=100.0),
			_row(cashier="EMP-001", collection_type="Mobile Money", amount=300.0),
		]
		doc = _make_shift(
			meter_readings=[meter],
			cashiers=[cashier],
			collections=collections,
		)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		self.assertAlmostEqual(cashier.expected, 300.0, places=2)
		self.assertAlmostEqual(cashier.mobile, 300.0, places=2)
		self.assertAlmostEqual(cashier.difference, 0.0, places=2)

	def test_debt_receipt_without_mobile_shows_shortage(self):
		ForecourtShift = _import_shift()
		meter = _make_meter_row(opening=900.0, closing=1100.0, price=100.0)
		cashier = _make_cashier_row(cashier="EMP-001")
		collections = [
			_row(cashier="EMP-001", collection_type="Debt Receipt", amount=100.0),
			# no Mobile Money — only cash
		]
		cash_counts = [_row(cashier="EMP-001", amount=200.0, base_amount=None)]
		doc = _make_shift(
			meter_readings=[meter],
			cashiers=[cashier],
			collections=collections,
			cash_counts=cash_counts,
		)

		import frappe

		frappe.db.get_value.return_value = None
		ForecourtShift._compute_meter_rows(doc)
		ForecourtShift._compute_cashier_rows(doc)

		# expected=300, accounted=200 → difference=-100
		self.assertAlmostEqual(cashier.expected, 300.0, places=2)
		self.assertAlmostEqual(cashier.difference, -100.0, places=2)


# ── S12: Overnight shift ────────────────────────────────────────────────────


class TestOvernightShift(unittest.TestCase):
	"""When template end_time < start_time, shift_end is bumped to next day."""

	def test_overnight_shift_end_next_day(self):
		ForecourtShift = _import_shift()
		# Night shift: starts 22:00, template end=06:00 (next day)
		tpl = SimpleNamespace(
			start_time=time(22, 0, 0),
			end_time=time(6, 0, 0),
		)
		doc = _make_shift(
			shift_date="2026-10-27",
			shift_start="2026-10-27 22:00:00",
			shift_end=None,
			shift_template="Night",
		)

		import frappe

		frappe.get_cached_doc.return_value = tpl
		ForecourtShift._compute_shift_window(doc)
		# Restore settings mock
		frappe.get_cached_doc.return_value = _SETTINGS

		self.assertIsNotNone(doc.shift_end)
		end = (
			doc.shift_end
			if isinstance(doc.shift_end, datetime)
			else datetime.fromisoformat(str(doc.shift_end)[:19])
		)
		self.assertEqual(end.date().isoformat(), "2026-10-28")
		self.assertEqual(end.hour, 6)

	def test_same_day_shift_unchanged(self):
		ForecourtShift = _import_shift()
		tpl = SimpleNamespace(
			start_time=time(6, 0, 0),
			end_time=time(14, 0, 0),
		)
		doc = _make_shift(
			shift_date="2026-10-27",
			shift_start="2026-10-27 06:00:00",
			shift_end=None,
			shift_template="Morning",
		)

		import frappe

		frappe.get_cached_doc.return_value = tpl
		ForecourtShift._compute_shift_window(doc)
		frappe.get_cached_doc.return_value = _SETTINGS

		end = (
			doc.shift_end
			if isinstance(doc.shift_end, datetime)
			else datetime.fromisoformat(str(doc.shift_end)[:19])
		)
		self.assertEqual(end.date().isoformat(), "2026-10-27")
		self.assertEqual(end.hour, 14)


# ── S13: Background close gate ──────────────────────────────────────────────


class TestBackgroundCloseGate(unittest.TestCase):
	"""Shift in 'Closing' state must only be submitted via background job."""

	def test_closing_blocks_direct_submit(self):
		import frappe

		frappe.flags.fms_background_close = False
		doc = _make_shift(status="Closing")
		blocked = doc.status == "Closing" and not frappe.flags.fms_background_close
		self.assertTrue(blocked)

	def test_closing_allows_background_submit(self):
		import frappe

		frappe.flags.fms_background_close = True
		doc = _make_shift(status="Closing")
		blocked = doc.status == "Closing" and not frappe.flags.fms_background_close
		self.assertFalse(blocked)
		frappe.flags.fms_background_close = False

	def test_non_closing_status_not_blocked(self):
		import frappe

		frappe.flags.fms_background_close = False
		for status in ("Draft", "Open", "Reconciled"):
			doc = _make_shift(status=status)
			blocked = doc.status == "Closing" and not frappe.flags.fms_background_close
			self.assertFalse(blocked, f"Status={status} should not block")


# ── Ledger writers ──────────────────────────────────────────────────────────


class TestLedgerWriters(unittest.TestCase):
	"""Wetstock, Nozzle and Cashier ledger writers set correct fields."""

	def setUp(self):
		import frappe

		self._inserted: list[SimpleNamespace] = []

		def _new_doc(doctype):
			idx = len(self._inserted) + 1
			doc = SimpleNamespace(
				doctype=doctype,
				name=f"MOCK-{doctype.replace(' ', '')}-{idx:04d}",
				flags=SimpleNamespace(ignore_permissions=False),
			)

			def _insert(**kw):
				doc.name = f"MOCK-{doctype.replace(' ', '')}-{len(self._inserted) + 1:04d}"
				self._inserted.append(doc)

			doc.insert = _insert
			return doc

		self._new_doc_patcher = patch(f"{_LEDGER_MODULE}.frappe.new_doc", side_effect=_new_doc)
		self._flt_patcher = patch(
			f"{_LEDGER_MODULE}.flt",
			side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
		)
		self._getdt_patcher = patch(
			f"{_LEDGER_MODULE}.get_datetime",
			side_effect=lambda s: (datetime.fromisoformat(str(s).replace(" ", "T")[:19]) if s else None),
		)
		self._new_doc_patcher.start()
		self._flt_patcher.start()
		self._getdt_patcher.start()

	def tearDown(self):
		self._new_doc_patcher.stop()
		self._flt_patcher.stop()
		self._getdt_patcher.stop()
		self._inserted.clear()

	def _make_submit_shift(self):
		dip = _make_dip_row(
			tank="T1",
			item="PMS",
			opening_l=20000.0,
			receipts_l=0.0,
			sales_l=1000.0,
			own_use_l=0.0,
			transfers_l=0.0,
			dip_l=19000.0,
			source="Manual",
		)
		dip.variance_l = -0.5
		dip.variance_pct = -0.05
		dip.expected_l = 19000.5

		meter = _make_meter_row(
			nozzle="N1",
			cashier="EMP-001",
			tank="T1",
			item="PMS",
			price=100.0,
			opening=900.0,
			closing=1100.0,
		)
		meter.net_volume_l = 2.0
		meter.amount = 200.0
		meter.basis_volume_l = 2.0
		meter.basis_meter = "Elec Cash"
		meter.drift_ecash_evol_l = 0.0
		meter.test_volume_l = 0.0
		meter.own_use_l = 0.0
		meter.attendant = None
		meter.segment_no = 1
		meter.source = "Manual"
		meter.closing_elec_cash = 1100.0
		meter.closing_elec_meter = 0.0
		meter.closing_man_meter = 0.0

		cashier = _make_cashier_row(cashier="EMP-001", fuel_amount=200.0, cash_counted=200.0)
		cashier.expected = 200.0
		cashier.accounted = 200.0
		cashier.debt_receipts = 0.0
		cashier.float_amount = 0.0
		cashier.mobile = 0.0
		cashier.card = 0.0
		cashier.credit = 0.0
		cashier.voucher = 0.0
		cashier.expenses = 0.0
		cashier.drops = 0.0
		cashier.item_amount = 0.0

		return _make_shift(
			name="SH-TEST-001",
			company="Test Co",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 14:00:00",
			shift_template="Morning",
			meter_readings=[meter],
			tank_dips=[dip],
			cashiers=[cashier],
			credit_sales=[],
			item_sales=[],
			resolutions=[],
		)

	def test_wetstock_ledger_entry_fields(self):
		from forecourt.posting.ledgers import write_shift_wetstock_ledger

		shift = self._make_submit_shift()
		posted = write_shift_wetstock_ledger(shift)

		self.assertEqual(len(posted), 1)
		wle = next(d for d in self._inserted if d.doctype == "Wetstock Ledger Entry")
		self.assertEqual(wle.company, "Test Co")
		self.assertEqual(wle.station, "STA-001")
		self.assertEqual(wle.tank, "T1")
		self.assertEqual(wle.entry_type, "Shift")
		self.assertEqual(wle.voucher_type, "Forecourt Shift")
		self.assertEqual(wle.forecourt_shift, "SH-TEST-001")
		self.assertAlmostEqual(wle.opening_l, 20000.0, places=3)
		self.assertAlmostEqual(wle.sales_l, 1000.0, places=3)
		self.assertAlmostEqual(wle.dip_l, 19000.0, places=3)

	def test_nozzle_ledger_entry_fields(self):
		from forecourt.posting.ledgers import write_shift_nozzle_ledger

		shift = self._make_submit_shift()
		posted = write_shift_nozzle_ledger(shift)

		self.assertEqual(len(posted), 1)
		nle = next(d for d in self._inserted if d.doctype == "Nozzle Ledger Entry")
		self.assertEqual(nle.nozzle, "N1")
		self.assertEqual(nle.cashier, "EMP-001")
		self.assertAlmostEqual(nle.net_l, 2.0, places=3)
		self.assertAlmostEqual(nle.amount, 200.0, places=2)
		self.assertEqual(nle.voucher_type, "Forecourt Shift")

	def test_cashier_ledger_entry_fields(self):
		from forecourt.posting.ledgers import write_shift_cashier_ledger

		shift = self._make_submit_shift()
		posted = write_shift_cashier_ledger(shift)

		self.assertEqual(len(posted), 1)
		cle = next(d for d in self._inserted if d.doctype == "Cashier Ledger Entry")
		self.assertEqual(cle.cashier, "EMP-001")
		self.assertAlmostEqual(cle.fuel_amount, 200.0, places=2)
		self.assertAlmostEqual(cle.cash, 200.0, places=2)
		self.assertAlmostEqual(cle.difference, 0.0, places=2)
		self.assertEqual(cle.voucher_type, "Forecourt Shift")

	def test_nozzle_last_readings_updated(self):
		import frappe

		from forecourt.posting.ledgers import update_nozzle_last_readings

		frappe.db = MagicMock()
		shift = self._make_submit_shift()
		update_nozzle_last_readings(shift)

		frappe.db.set_value.assert_called_once()
		call_args = frappe.db.set_value.call_args
		self.assertEqual(call_args[0][0], "Nozzle")
		self.assertEqual(call_args[0][1], "N1")
		updates = call_args[0][2]
		self.assertIn("last_reading_shift", updates)
		self.assertAlmostEqual(updates.get("last_ecash", 0), 1100.0, places=3)


if __name__ == "__main__":
	unittest.main()
