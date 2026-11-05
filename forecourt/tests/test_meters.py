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


if __name__ == "__main__":
	unittest.main()
