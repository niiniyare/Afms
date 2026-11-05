# Tests for FMS-D04: meter drift
from __future__ import annotations

import unittest

from forecourt.calc.drift import ecash_vs_evol, ecash_vs_mvol, evol_vs_mvol, within_tolerance


class TestDriftFormulas(unittest.TestCase):
	def test_evol_vs_mvol_positive(self) -> None:
		self.assertAlmostEqual(evol_vs_mvol(1000.0, 998.0), 2.0)

	def test_evol_vs_mvol_negative(self) -> None:
		self.assertAlmostEqual(evol_vs_mvol(990.0, 1000.0), -10.0)

	def test_ecash_vs_evol(self) -> None:
		self.assertAlmostEqual(ecash_vs_evol(1000.0, 995.0), 5.0)

	def test_ecash_vs_mvol(self) -> None:
		self.assertAlmostEqual(ecash_vs_mvol(1000.0, 992.0), 8.0)

	def test_zero_drift(self) -> None:
		self.assertAlmostEqual(evol_vs_mvol(1000.0, 1000.0), 0.0)


class TestWithinTolerance(unittest.TestCase):
	def test_within_abs_limit(self) -> None:
		self.assertTrue(within_tolerance(1.0, basis_litres=10.0, tol_pct=0.5, tol_l=2.0))

	def test_outside_abs_and_pct(self) -> None:
		# 20 L drift on 2000 L: pct limit = 10 L, abs = 2 L; max = 10; 20 > 10 → fail
		self.assertFalse(within_tolerance(20.0, 2000.0, tol_pct=0.5, tol_l=2.0))

	def test_abs_dominates_small_sales(self) -> None:
		# 1.5 L on 10 L: pct limit = 0.05 L, abs = 2 L; max = 2; 1.5 ≤ 2 → pass
		self.assertTrue(within_tolerance(1.5, 10.0, tol_pct=0.5, tol_l=2.0))

	def test_pct_dominates_large_sales(self) -> None:
		# 8 L on 2000 L: pct limit = 10, abs = 2; max = 10; 8 ≤ 10 → pass
		self.assertTrue(within_tolerance(8.0, 2000.0, tol_pct=0.5, tol_l=2.0))

	def test_exactly_at_pct_limit(self) -> None:
		# 10 L on 2000 L: limit = max(10, 2) = 10; 10 ≤ 10 → pass
		self.assertTrue(within_tolerance(10.0, 2000.0, tol_pct=0.5, tol_l=2.0))

	def test_negative_drift_within(self) -> None:
		self.assertTrue(within_tolerance(-1.0, 2000.0, tol_pct=0.5, tol_l=2.0))

	def test_zero_drift(self) -> None:
		self.assertTrue(within_tolerance(0.0, 2000.0))


if __name__ == "__main__":
	unittest.main()
