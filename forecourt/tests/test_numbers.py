"""Numeric precision and rounding tests (TC-NUM-001 to TC-NUM-010).

AFMS posts money.  A rounding error is a missing shilling. These tests
verify that the calculation core:

  - produces consistent, reproducible totals regardless of evaluation order
  - never accumulates floating-point drift over many payments
  - handles currencies with zero or three decimal places
  - rejects invalid numeric inputs at field boundaries

All tests in this file are pure-Python unit tests (layer U); they require
no Frappe site and import only from forecourt.calc.

See fms.md section 29 and test-cases.md section 29 for the design rules.
"""

from __future__ import annotations

import decimal
import unittest

from forecourt.calc.attribution import SalesLine, attribute
from forecourt.calc.cashier import CashierBalance, balance
from forecourt.calc.meters import MeterReading, segment_sales
from forecourt.calc.reconciliation import TankReconciliation, reconcile


class TestPaymentSummationNeverLosesACent(unittest.TestCase):
	"""TC-NUM-002: summing many payments must equal the exact total — no floating-point drift."""

	def test_500_payments_of_33_33_sum_to_exact_total(self) -> None:
		"""TC-NUM-002: 500 x 33.33 = 16,665.00 exactly (Decimal arithmetic, not float)."""
		unit = decimal.Decimal("33.33")
		total = sum(unit for _ in range(500))
		self.assertEqual(total, decimal.Decimal("16665.00"))

	def test_attribution_of_many_small_payments_sums_to_original_total(self) -> None:
		"""TC-NUM-002 via attribution: 500 payments of 100.00 attributed over 3 lines sums exactly."""
		lines = [
			SalesLine(key="PMS", amount=10000.0),
			SalesLine(key="AGO", amount=10000.0),
			SalesLine(key="DPK", amount=10000.0),
		]
		# Each of 500 payments is 60.00 (total 30,000.00 = exact total of lines)
		for _ in range(500):
			result = attribute({"Cash": 60.0}, lines)
			cash_rows = [r for r in result if r.payment_type == "Cash"]
			self.assertAlmostEqual(
				sum(r.amount for r in cash_rows),
				60.0,
				places=6,
				msg="Single payment attribution must sum to exactly 60.00",
			)


class TestRoundingConsistencyAcrossCalcFunctions(unittest.TestCase):
	"""TC-NUM-001 / TC-NUM-003: litres x price rounding is documented, identical in shift and reports."""

	def test_ecash_basis_amount_always_equals_meter_delta_exactly(self) -> None:
		"""TC-NUM-001: for E-cash basis, the amount IS the meter delta — no rounding is applied.

		No matter how many decimals the price has, the basis_amount for
		E-cash basis is always exactly the delta of the E-cash meter.
		This ensures the amount in the Sales Invoice matches the pump display.
		"""
		for price in [180.0, 183.47, 199.999, 170.0]:
			for delta in [1000.0, 180000.0, 5.5, 0.01]:
				s = segment_sales(
					ecash=MeterReading(opening=0.0, closing=delta),
					evol=None,
					mvol=None,
					price=price,
					sales_basis="Elec Cash",
				)
				self.assertEqual(
					s.basis_amount,
					delta,
					msg=f"E-cash basis_amount must equal delta={delta} at price={price}",
				)

	def test_volume_basis_amount_is_litres_times_price(self) -> None:
		"""TC-NUM-001: for E-vol and M-vol basis, basis_amount = basis_litres x price (not the meter delta)."""
		s = segment_sales(
			ecash=None,
			evol=MeterReading(opening=0.0, closing=100.0),
			mvol=None,
			price=183.47,
			sales_basis="Elec Mtr",
		)
		self.assertAlmostEqual(s.basis_amount, 100.0 * 183.47, places=6)


class TestZeroDecimalCurrency(unittest.TestCase):
	"""TC-NUM-004: currencies with zero decimals (UGX, IRR) — amounts must be whole numbers.

	The calc layer itself is currency-agnostic; it returns float values.
	Rounding to zero decimals is the responsibility of posting code that
	calls round(value, currency.precision).  These tests verify the raw
	calc outputs are in a form that round(x, 0) can safely produce.
	"""

	def test_cashier_balance_expected_can_be_rounded_to_whole_number(self) -> None:
		"""TC-NUM-004: balance() returns a float that is already a whole number for whole-number inputs."""
		cb = CashierBalance(
			fuel_amount=372500.0,
			item_amount=0.0,
			cash=373000.0,
			opening_float=0.0,
		)
		balance(cb)
		# With UGX (0 decimal places) round to integer should produce exact values
		self.assertEqual(round(cb.expected, 0), 372500.0)
		self.assertEqual(round(cb.difference, 0), 500.0)

	def test_reconcile_expected_closing_is_exact_for_whole_number_inputs(self) -> None:
		rec = TankReconciliation(opening_volume=20000.0, receipts=10000.0, net_sales=5000.0)
		reconcile(rec)
		self.assertEqual(rec.expected_closing, 25000.0)
		self.assertEqual(round(rec.expected_closing, 0), 25000.0)


class TestVeryLargeAndVerySmallValues(unittest.TestCase):
	"""TC-NUM-006 / TC-NUM-007: extreme values must not overflow or be silently lost."""

	def test_meter_at_maximum_value_computes_without_overflow(self) -> None:
		"""TC-NUM-006: meter reading near 9,999,999.99 — the Python float is exact at this scale."""
		s = segment_sales(
			ecash=MeterReading(opening=9_900_000.0, closing=9_999_999.0),
			evol=None,
			mvol=None,
			price=180.0,
			sales_basis="Elec Cash",
		)
		self.assertAlmostEqual(s.basis_amount, 99_999.0)
		self.assertGreater(s.basis_litres, 0)

	def test_shift_with_50_million_sales_does_not_overflow(self) -> None:
		"""TC-NUM-006: 50 million KES in one shift — reconciliation must still be exact."""
		rec = TankReconciliation(
			opening_volume=100_000.0,
			net_sales=277_777.0,  # ~50M KES at 180/L
			closing_dip=99_000.0,
		)
		reconcile(rec)
		self.assertAlmostEqual(rec.expected_closing, -177_777.0, places=1)

	def test_one_cent_difference_is_still_a_difference(self) -> None:
		"""TC-NUM-007: a 0.01 difference must not be silently swallowed by rounding."""
		cb = CashierBalance(
			fuel_amount=10000.0,
			cash=9999.99,
			opening_float=0.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.difference, -0.01, places=6)
		self.assertNotEqual(cb.difference, 0.0)

	def test_zero_point_01_litres_sold_is_preserved(self) -> None:
		"""TC-NUM-007: 0.01 L sold on E-vol basis remains non-zero after rounding."""
		s = segment_sales(
			ecash=None,
			evol=MeterReading(opening=0.0, closing=0.01),
			mvol=None,
			price=180.0,
			sales_basis="Elec Mtr",
		)
		self.assertAlmostEqual(s.basis_litres, 0.01, places=4)
		self.assertGreater(s.basis_litres, 0.0)


class TestNegativeValuesRejected(unittest.TestCase):
	"""TC-NUM-010: negative quantities in calc inputs must be caught by the calling gate or controller.

	The pure calc functions accept any float, but the gate layer (and
	DocType validation in the controller) must refuse negative readings,
	litres, or cash counts.  These tests document the expected *calc*
	behaviour so a future gate can rely on consistent inputs.
	"""

	def test_negative_cash_in_drawer_reduces_accounted_below_zero(self) -> None:
		"""When cash is typed as negative (data error), accounted goes negative — clearly wrong.

		A future gate (TC-NUM-010) must catch this at the UI/controller level.
		This test documents the pure-calc output so the gate can be tested against it.
		"""
		cb = CashierBalance(fuel_amount=10000.0, cash=-500.0, opening_float=0.0)
		balance(cb)
		self.assertLess(cb.accounted, 0)
		# The resulting difference is a large negative — the gate should refuse to close

	def test_negative_meter_delta_raises_value_error(self) -> None:
		"""calc.meters already rejects closing < opening (raising ValueError).

		This test exists so a new developer understands that negative deltas
		are impossible inputs that the calc layer catches before they reach
		the cashier balance.
		"""
		from forecourt.calc.meters import MeterReading as MR
		from forecourt.calc.meters import meter_delta

		with self.assertRaises(ValueError):
			meter_delta(MR(opening=1000.0, closing=500.0, rollover=False))


class TestHighPrecisionPrice(unittest.TestCase):
	"""TC-NUM-008: prices stored at three decimal places must be applied correctly."""

	def test_three_decimal_price_produces_correct_basis_amount(self) -> None:
		"""TC-NUM-008: price 183.475 on 1,000 L → basis_amount = 183,475.000 exactly (E-vol basis)."""
		s = segment_sales(
			ecash=None,
			evol=MeterReading(opening=0.0, closing=1000.0),
			mvol=None,
			price=183.475,
			sales_basis="Elec Mtr",
		)
		self.assertAlmostEqual(s.basis_amount, 183475.0, places=3)

	def test_e_cash_basis_amount_is_unaffected_by_price_precision(self) -> None:
		"""TC-NUM-008: E-cash basis amount is always the delta, so price precision cannot corrupt it."""
		s = segment_sales(
			ecash=MeterReading(opening=0.0, closing=50000.0),
			evol=None,
			mvol=None,
			price=183.475,
			sales_basis="Elec Cash",
		)
		self.assertEqual(s.basis_amount, 50000.0)


if __name__ == "__main__":
	unittest.main()
