# Tests for FMS-D05: tank reconciliation
from __future__ import annotations

import unittest

from forecourt.calc.reconciliation import TankReconciliation, reconcile, within_tolerance


class TestReconcile(unittest.TestCase):
	def test_basic(self) -> None:
		rec = TankReconciliation(
			opening_volume=20000.0,
			receipts=10000.0,
			net_sales=5000.0,
			closing_dip=25050.0,
		)
		reconcile(rec)
		self.assertAlmostEqual(rec.expected_closing, 25000.0)
		self.assertAlmostEqual(rec.variance, 50.0)
		self.assertAlmostEqual(rec.variance_pct, 1.0)

	def test_no_dip_no_variance(self) -> None:
		rec = TankReconciliation(opening_volume=20000.0, net_sales=5000.0)
		reconcile(rec)
		self.assertIsNone(rec.variance)
		self.assertIsNone(rec.variance_pct)

	def test_zero_sales_variance_pct_none(self) -> None:
		rec = TankReconciliation(opening_volume=10000.0, closing_dip=10010.0)
		reconcile(rec)
		self.assertAlmostEqual(rec.variance, 10.0)
		self.assertIsNone(rec.variance_pct)

	def test_transfer_out(self) -> None:
		rec = TankReconciliation(opening_volume=10000.0, transfers=-500.0, closing_dip=9500.0)
		reconcile(rec)
		self.assertAlmostEqual(rec.expected_closing, 9500.0)
		self.assertAlmostEqual(rec.variance, 0.0)

	def test_own_use_reduces_expected(self) -> None:
		rec = TankReconciliation(
			opening_volume=15000.0,
			receipts=10000.0,
			net_sales=8000.0,
			own_use=50.0,
			closing_dip=16970.0,
		)
		reconcile(rec)
		self.assertAlmostEqual(rec.expected_closing, 16950.0)
		self.assertAlmostEqual(rec.variance, 20.0)

	def test_negative_variance_loss(self) -> None:
		rec = TankReconciliation(opening_volume=10000.0, net_sales=1000.0, closing_dip=8900.0)
		reconcile(rec)
		self.assertAlmostEqual(rec.variance, -100.0)
		self.assertAlmostEqual(rec.variance_pct, -10.0)


class TestWithinTolerance(unittest.TestCase):
	def test_within_abs_default(self) -> None:
		self.assertTrue(within_tolerance(15.0, net_sales=100.0))

	def test_outside_abs_within_pct(self) -> None:
		# 25 L > 20 L abs, but 25 / 5000 = 0.5% exactly → limit = max(20, 25) = 25 → pass
		self.assertTrue(within_tolerance(25.0, net_sales=5000.0))

	def test_outside_both(self) -> None:
		self.assertFalse(within_tolerance(150.0, net_sales=5000.0))

	def test_pct_limit_dominates_large_sales(self) -> None:
		# 40 L on 10000 L: pct limit = 50 > 20 abs; 40 ≤ 50 → pass
		self.assertTrue(within_tolerance(40.0, net_sales=10000.0))

	def test_zero_sales_abs_only(self) -> None:
		self.assertTrue(within_tolerance(15.0, net_sales=0.0))
		self.assertFalse(within_tolerance(25.0, net_sales=0.0))


if __name__ == "__main__":
	unittest.main()
