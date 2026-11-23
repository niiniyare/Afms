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

	# ------------------------------------------------------------------ TC-CAL-052 to 060

	def test_zero_sales_with_small_negative_variance_is_within_tolerance(self) -> None:
		"""TC-CAL-052: net sales zero, variance -5 L → within tolerance (absolute limit 20 L applies)."""
		self.assertTrue(within_tolerance(-5.0, net_sales=0.0))

	def test_variance_negative_quarter_percent_on_large_sales_is_within_tolerance(self) -> None:
		"""TC-CAL-053: -25 L on 10,000 L (-0.25%) → pct limit = 50 L, abs = 20 L; limit = 50 L → pass."""
		self.assertTrue(within_tolerance(-25.0, net_sales=10000.0))

	def test_variance_negative_half_percent_on_large_sales_is_exactly_at_boundary(self) -> None:
		"""TC-CAL-056: -50 L on 10,000 L (-0.5%) is exactly at the tolerance boundary → pass (inclusive)."""
		self.assertTrue(within_tolerance(-50.0, net_sales=10000.0))

	def test_variance_outside_tolerance_requires_reason(self) -> None:
		"""TC-CAL-054: -60 L on 10,000 L (-0.6%) exceeds 0.5% limit of 50 L → outside tolerance."""
		self.assertFalse(within_tolerance(-60.0, net_sales=10000.0))

	def test_variance_beyond_approval_threshold_needs_approval(self) -> None:
		"""TC-CAL-055: -101 L on 10,000 L — approval threshold is 2x tolerance = 100 L.

		within_tolerance only checks the ±50 L / ±0.5% band.  The approval check
		(needs_approval flag) is applied separately by the controller; here we
		verify that -101 L is correctly flagged as outside tolerance.
		"""
		self.assertFalse(within_tolerance(-101.0, net_sales=10000.0))

	def test_positive_variance_same_rules_as_negative(self) -> None:
		"""TC-CAL-057: tolerance is symmetric — a positive gain of the same size is treated identically."""
		# +25 L on 10,000 L → within tolerance (same as TC-CAL-053)
		self.assertTrue(within_tolerance(25.0, net_sales=10000.0))
		# +60 L → outside tolerance (same as TC-CAL-054)
		self.assertFalse(within_tolerance(60.0, net_sales=10000.0))

	def test_custom_tolerance_parameters_override_defaults(self) -> None:
		"""TC-CAL-058: tolerance settings can be overridden per tank, station or company.

		Passing explicit tol_pct and tol_l verifies the formula uses the supplied values.
		"""
		# With tighter tolerance: 1% pct, 5 L abs
		self.assertTrue(within_tolerance(4.0, net_sales=1000.0, tol_pct=1.0, tol_l=5.0))
		self.assertFalse(within_tolerance(11.0, net_sales=1000.0, tol_pct=1.0, tol_l=5.0))


class TestReconcileAdditionalCases(unittest.TestCase):
	"""TC-CAL-050 to TC-CAL-060 — reconciliation corner cases."""

	def test_no_dip_means_no_variance_calculated(self) -> None:
		"""TC-CAL-060: when no dip is taken the template does not require one; variance stays None."""
		rec = TankReconciliation(opening_volume=10000.0, net_sales=1000.0)  # closing_dip not set
		reconcile(rec)
		self.assertIsNone(rec.variance)
		self.assertIsNone(rec.variance_pct)
		self.assertAlmostEqual(rec.expected_closing, 9000.0)

	def test_variance_percent_is_none_when_net_sales_zero(self) -> None:
		"""TC-CAL-052 reconcile part: variance % is undefined (None) when sales = 0 — no division by zero."""
		rec = TankReconciliation(opening_volume=10000.0, closing_dip=9995.0)  # net_sales defaults to 0
		reconcile(rec)
		self.assertAlmostEqual(rec.variance, -5.0)
		self.assertIsNone(rec.variance_pct)

	def test_variance_percent_sign_follows_the_variance_sign(self) -> None:
		"""TC-CAL-051: sign is preserved — a loss gives a negative %, a gain gives a positive %."""
		rec_loss = TankReconciliation(opening_volume=10000.0, net_sales=5000.0, closing_dip=4900.0)
		reconcile(rec_loss)
		self.assertLess(rec_loss.variance, 0)
		self.assertLess(rec_loss.variance_pct, 0)

		rec_gain = TankReconciliation(opening_volume=10000.0, net_sales=5000.0, closing_dip=5200.0)
		reconcile(rec_gain)
		self.assertGreater(rec_gain.variance, 0)
		self.assertGreater(rec_gain.variance_pct, 0)


if __name__ == "__main__":
	unittest.main()
