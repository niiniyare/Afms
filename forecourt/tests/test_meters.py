# Tests for FMS-D03: meter deltas, rollover and sales basis
from __future__ import annotations

import unittest

from forecourt.calc.meters import MeterReading, meter_delta, segment_sales


class TestMeterDelta(unittest.TestCase):
	def test_simple(self) -> None:
		r = MeterReading(opening=1000.0, closing=1500.0)
		self.assertAlmostEqual(meter_delta(r), 500.0)

	def test_zero_delta(self) -> None:
		r = MeterReading(opening=1000.0, closing=1000.0)
		self.assertAlmostEqual(meter_delta(r), 0.0)

	def test_rollover(self) -> None:
		r = MeterReading(opening=9990.0, closing=10.0, rollover_max=10000.0, rollover=True)
		self.assertAlmostEqual(meter_delta(r), 20.0)

	def test_closing_below_opening_no_rollover_raises(self) -> None:
		r = MeterReading(opening=1000.0, closing=500.0)
		with self.assertRaises(ValueError):
			meter_delta(r)

	def test_rollover_without_max_raises(self) -> None:
		r = MeterReading(opening=9990.0, closing=10.0, rollover_max=0.0, rollover=True)
		with self.assertRaises(ValueError):
			meter_delta(r)

	def test_closing_exceeds_rollover_max_raises(self) -> None:
		r = MeterReading(opening=9990.0, closing=10001.0, rollover_max=10000.0, rollover=True)
		with self.assertRaises(ValueError):
			meter_delta(r)


class TestSegmentSales(unittest.TestCase):
	def test_elec_cash_basis(self) -> None:
		s = segment_sales(
			ecash=MeterReading(0.0, 180000.0),
			evol=None,
			mvol=None,
			price=180.0,
			sales_basis="Elec Cash",
		)
		self.assertAlmostEqual(s.ecash_delta, 180000.0)
		self.assertAlmostEqual(s.basis_litres, 1000.0)
		self.assertAlmostEqual(s.basis_amount, 180000.0)
		self.assertEqual(s.basis, "Elec Cash")

	def test_elec_mtr_basis(self) -> None:
		s = segment_sales(
			ecash=None,
			evol=MeterReading(0.0, 1000.0),
			mvol=None,
			price=180.0,
			sales_basis="Elec Mtr",
		)
		self.assertAlmostEqual(s.basis_litres, 1000.0)
		self.assertAlmostEqual(s.basis_amount, 180000.0)
		self.assertEqual(s.basis, "Elec Mtr")

	def test_man_mtr_basis(self) -> None:
		s = segment_sales(
			ecash=None,
			evol=None,
			mvol=MeterReading(0.0, 950.0),
			price=180.0,
			sales_basis="Man Mtr",
		)
		self.assertAlmostEqual(s.basis_litres, 950.0)
		self.assertEqual(s.basis, "Man Mtr")

	def test_highest_picks_ecash_when_largest(self) -> None:
		s = segment_sales(
			ecash=MeterReading(0.0, 180000.0),
			evol=MeterReading(0.0, 900.0),
			mvol=MeterReading(0.0, 950.0),
			price=180.0,
			sales_basis="Highest",
		)
		self.assertEqual(s.basis, "Elec Cash")
		self.assertAlmostEqual(s.basis_litres, 1000.0)

	def test_highest_picks_mvol_when_largest(self) -> None:
		s = segment_sales(
			ecash=MeterReading(0.0, 90000.0),
			evol=MeterReading(0.0, 480.0),
			mvol=MeterReading(0.0, 600.0),
			price=180.0,
			sales_basis="Highest",
		)
		self.assertEqual(s.basis, "Man Mtr")
		self.assertAlmostEqual(s.basis_litres, 600.0)

	def test_invalid_basis_raises(self) -> None:
		with self.assertRaises(ValueError):
			segment_sales(
				ecash=MeterReading(0.0, 100.0),
				evol=None,
				mvol=None,
				price=180.0,
				sales_basis="Unknown",
			)

	def test_zero_price_raises(self) -> None:
		with self.assertRaises(ValueError):
			segment_sales(
				ecash=MeterReading(0.0, 100.0),
				evol=None,
				mvol=None,
				price=0.0,
				sales_basis="Elec Cash",
			)

	def test_rollover_ecash(self) -> None:
		"""TC-CAL-004 / rollover path: (max - opening) + closing."""
		s = segment_sales(
			ecash=MeterReading(
				opening=9999000.0,
				closing=1000.0,
				rollover_max=9999999.0,
				rollover=True,
			),
			evol=None,
			mvol=None,
			price=180.0,
			sales_basis="Elec Cash",
		)
		expected_delta = (9999999.0 - 9999000.0) + 1000.0
		self.assertAlmostEqual(s.ecash_delta, expected_delta)

	def test_TC_CAL_008_rollover_ecash_only_evol_normal(self) -> None:
		"""TC-CAL-008: rollover on e-cash only; e-vol computed without rollover."""
		s = segment_sales(
			ecash=MeterReading(opening=9999000.0, closing=100.0, rollover_max=9999999.0, rollover=True),
			evol=MeterReading(opening=100.0, closing=600.0),
			mvol=None,
			price=180.0,
			sales_basis="Highest",
		)
		expected_ecash_delta = (9999999.0 - 9999000.0) + 100.0  # = 1099
		expected_ecash_litres = expected_ecash_delta / 180.0
		self.assertAlmostEqual(s.ecash_delta, expected_ecash_delta)
		self.assertAlmostEqual(s.ecash_litres, expected_ecash_litres)
		self.assertAlmostEqual(s.evol_delta, 500.0)
		self.assertAlmostEqual(s.evol_litres, 500.0)
		# basis: ecash_litres ≈ 6.1 L, evol_litres = 500 L → Elec Mtr wins
		self.assertEqual(s.basis, "Elec Mtr")
		self.assertAlmostEqual(s.basis_litres, 500.0)

	def test_TC_CAL_010_ecash_basis_amount_exact_with_non_round_price(self) -> None:
		"""TC-CAL-010: E-cash basis — amount stays exactly the meter delta, no float drift.

		Δ 1,000.00 at 183.47 → litres = 1000/183.47 (rounded), but amount = 1000.00 exactly.
		"""
		price = 183.47
		s = segment_sales(
			ecash=MeterReading(opening=0.0, closing=1000.0),
			evol=None,
			mvol=None,
			price=price,
			sales_basis="Elec Cash",
		)
		self.assertAlmostEqual(s.ecash_delta, 1000.0)
		self.assertAlmostEqual(s.basis_amount, 1000.0)
		# litres = delta / price — not exactly round, but stored at field precision
		expected_litres = 1000.0 / price
		self.assertAlmostEqual(s.basis_litres, expected_litres, places=6)
		self.assertEqual(s.basis, "Elec Cash")

	def test_TC_CAL_013_highest_tiebreak_ecash_wins(self) -> None:
		"""TC-CAL-013: Highest tie-break — E-cash wins over E-vol when litres equal."""
		price = 100.0
		# ecash_litres = 500 / 100 = 5; evol_litres = 5; tie → E-cash wins (first candidate)
		s = segment_sales(
			ecash=MeterReading(opening=0.0, closing=500.0),
			evol=MeterReading(opening=0.0, closing=5.0),
			mvol=None,
			price=price,
			sales_basis="Highest",
		)
		self.assertEqual(s.basis, "Elec Cash")
		self.assertAlmostEqual(s.basis_litres, 5.0)

	def test_TC_CAL_013_highest_tiebreak_evol_beats_mvol(self) -> None:
		"""TC-CAL-013 variant: E-vol beats M-vol in a tie (order E-cash, E-vol, M-vol)."""
		price = 100.0
		# ecash absent; evol_litres = 10 = mvol_litres → E-vol wins
		s = segment_sales(
			ecash=None,
			evol=MeterReading(opening=0.0, closing=10.0),
			mvol=MeterReading(opening=0.0, closing=10.0),
			price=price,
			sales_basis="Highest",
		)
		self.assertEqual(s.basis, "Elec Mtr")

	def test_TC_CAL_017_net_sold_formula(self) -> None:
		"""TC-CAL-017: net sold = basis_litres - test - own_use.

		The calc layer returns basis_litres; the net subtraction is arithmetic.
		"""
		s = segment_sales(
			ecash=MeterReading(opening=0.0, closing=54000.0),  # 300 L at 180
			evol=None,
			mvol=None,
			price=180.0,
			sales_basis="Elec Cash",
		)
		test_volume_l = 5.0
		own_use_l = 20.0
		net_sold = s.basis_litres - test_volume_l - own_use_l
		self.assertAlmostEqual(net_sold, 275.0)

	def test_TC_CAL_019_elec_mtr_basis_no_evol_raises(self) -> None:
		"""TC-CAL-019: Elec Mtr basis with evol=None raises ValueError (FMS-M603 path)."""
		with self.assertRaises(ValueError):
			segment_sales(
				ecash=MeterReading(opening=0.0, closing=100.0),
				evol=None,
				mvol=None,
				price=180.0,
				sales_basis="Elec Mtr",
			)

	def test_TC_CAL_019_man_mtr_basis_no_mvol_raises(self) -> None:
		"""Man Mtr basis with mvol=None raises ValueError."""
		with self.assertRaises(ValueError):
			segment_sales(
				ecash=None,
				evol=None,
				mvol=None,
				price=180.0,
				sales_basis="Man Mtr",
			)

	def test_TC_CAL_019_highest_no_meters_raises(self) -> None:
		"""Highest basis with all meters None raises ValueError."""
		with self.assertRaises(ValueError):
			segment_sales(
				ecash=None,
				evol=None,
				mvol=None,
				price=180.0,
				sales_basis="Highest",
			)


class TestMeterDeltaOpenQuestions(unittest.TestCase):
	"""Proposed but not-yet-decided behaviours (Q-01, Q-02). Skipped until resolved."""

	@unittest.skip("Q-01 open: proposed — refuse rollover tick when closing >= opening")
	def test_TC_CAL_005_rollover_ticked_closing_above_opening_proposed_error(self) -> None:
		"""TC-CAL-005 (proposed): rollover=True but closing >= opening → ValueError.

		Current code: returns closing - opening normally.
		Proposed: refuse the tick, raise ValueError.
		"""
		r = MeterReading(opening=1000.0, closing=1500.0, rollover_max=9999999.0, rollover=True)
		with self.assertRaises(ValueError):
			meter_delta(r)

	@unittest.skip("Q-02 open: proposed — refuse full-cycle rollover (closing == opening)")
	def test_TC_CAL_006_rollover_full_cycle_proposed_error(self) -> None:
		"""TC-CAL-006 (proposed): rollover=True and closing == opening → ValueError.

		Current code: returns 0.0 (zero delta).
		Proposed: refuse (a nozzle cannot sell its full meter range in one shift).
		"""
		r = MeterReading(opening=1000.0, closing=1000.0, rollover_max=9999999.0, rollover=True)
		with self.assertRaises(ValueError):
			meter_delta(r)


if __name__ == "__main__":
	unittest.main()
