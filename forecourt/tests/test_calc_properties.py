"""Property tests for the calculation core (FMS-D08).

100 random runs each, no frappe imports.
"""

from __future__ import annotations

import random
import unittest

from forecourt.calc.attribution import SalesLine, attribute
from forecourt.calc.calibration import interpolate
from forecourt.calc.cashier import CashierBalance, balance
from forecourt.calc.drift import within_tolerance as drift_ok
from forecourt.calc.meters import MeterReading, meter_delta, segment_sales
from forecourt.calc.reconciliation import TankReconciliation, reconcile, within_tolerance

SEED = 42
RUNS = 100


class TestCalibrationMonotonic(unittest.TestCase):
	def test_interpolation_monotonic(self):
		rng = random.Random(SEED)
		for run in range(RUNS):
			n = rng.randint(2, 12)
			depths = sorted(rng.uniform(0, 5000) for _ in range(n))
			vols = [0.0]
			for _ in range(n - 1):
				vols.append(vols[-1] + rng.uniform(0.1, 500))
			rows = list(zip(depths, vols, strict=True))
			test_d = sorted(rng.uniform(depths[0], depths[-1]) for _ in range(6))
			results = [interpolate(d, rows) for d in test_d]
			for i in range(len(results) - 1):
				self.assertLessEqual(
					results[i],
					results[i + 1] + 1e-9,
					f"interpolate not monotonic at run {run}",
				)


class TestMeterDeltaProperties(unittest.TestCase):
	def test_no_rollover_non_negative(self):
		rng = random.Random(SEED + 1)
		for _ in range(RUNS):
			opening = rng.uniform(0, 999_999)
			delta = rng.uniform(0, 50_000)
			r = MeterReading(opening=opening, closing=opening + delta)
			self.assertGreaterEqual(meter_delta(r), 0)

	def test_rollover_equals_formula(self):
		rng = random.Random(SEED + 2)
		for _ in range(RUNS):
			max_val = rng.uniform(1_000, 9_999_999)
			opening = rng.uniform(0, max_val * 0.9)
			closing = rng.uniform(0, opening * 0.5)
			r = MeterReading(
				opening=opening,
				closing=closing,
				rollover_max=max_val,
				rollover=True,
			)
			self.assertAlmostEqual(
				meter_delta(r),
				(max_val - opening) + closing,
				places=6,
			)


class TestReconciliationProperties(unittest.TestCase):
	def test_expected_closing_formula(self):
		rng = random.Random(SEED + 3)
		for _ in range(RUNS):
			o = rng.uniform(0, 50_000)
			rcpts = rng.uniform(0, 30_000)
			sales = rng.uniform(0, min(o + rcpts, 25_000))
			own = rng.uniform(0, 300)
			trf = rng.uniform(-2_000, 2_000)
			rec = TankReconciliation(
				opening_volume=o,
				receipts=rcpts,
				net_sales=sales,
				own_use=own,
				transfers=trf,
			)
			reconcile(rec)
			self.assertAlmostEqual(
				rec.expected_closing,
				o + rcpts - sales - own + trf,
				places=6,
			)

	def test_variance_sign(self):
		rng = random.Random(SEED + 4)
		for _ in range(RUNS):
			o = rng.uniform(0, 50_000)
			sales = rng.uniform(100, 5_000)
			dip = rng.uniform(0, o + 5_000)
			rec = TankReconciliation(opening_volume=o, net_sales=sales, closing_dip=dip)
			reconcile(rec)
			self.assertAlmostEqual(rec.variance, dip - rec.expected_closing, places=6)


class TestCashierBalanceProperties(unittest.TestCase):
	def test_difference_formula(self):
		rng = random.Random(SEED + 5)
		for _ in range(RUNS):
			fuel = rng.uniform(0, 100_000)
			item = rng.uniform(0, 10_000)
			debt = rng.uniform(0, 5_000)
			cash = rng.uniform(0, 50_000)
			ofloat = rng.uniform(0, 2_000)
			mobile = rng.uniform(0, 20_000)
			card = rng.uniform(0, 20_000)
			credit = rng.uniform(0, 5_000)
			voucher = rng.uniform(0, 1_000)
			expenses = rng.uniform(0, 500)
			drops = rng.uniform(0, 1_000)
			cb = CashierBalance(
				fuel_amount=fuel,
				item_amount=item,
				debt_receipts=debt,
				cash=cash,
				mobile=mobile,
				card=card,
				credit=credit,
				voucher=voucher,
				expenses=expenses,
				drops=drops,
				opening_float=ofloat,
			)
			balance(cb)
			self.assertAlmostEqual(cb.expected, fuel + item + debt, places=6)
			self.assertAlmostEqual(
				cb.accounted,
				(cash - ofloat) + mobile + card + credit + voucher + expenses + drops,
				places=6,
			)
			self.assertAlmostEqual(cb.difference, cb.accounted - cb.expected, places=6)


class TestAttributionProperties(unittest.TestCase):
	def test_attribution_totals_match(self):
		rng = random.Random(SEED + 6)
		for run in range(RUNS):
			n_lines = rng.randint(2, 8)
			lines = [SalesLine(key=f"L{i}", amount=round(rng.uniform(200, 5_000), 2)) for i in range(n_lines)]
			total_sales = sum(l.amount for l in lines)
			w1, w2 = rng.random(), rng.random()
			if w1 + w2 > 1:
				w1, w2 = w1 / (w1 + w2 + 0.01), w2 / (w1 + w2 + 0.01)
			totals = {
				"Cash": round(total_sales * w1, 2),
				"Mobile": round(total_sales * w2, 2),
				"Card": round(total_sales - total_sales * w1 - total_sales * w2, 2),
			}
			rows = attribute(totals, lines)
			for ptype, expected_total in totals.items():
				got = sum(r.amount for r in rows if r.payment_type == ptype and r.basis == "Attributed")
				self.assertAlmostEqual(
					got,
					expected_total,
					places=4,
					msg=f"run={run} ptype={ptype}",
				)


class TestCalibrationExactChartPointProperty(unittest.TestCase):
	"""TC-PBT-004: for any point that is exactly on the chart, interpolate() returns that point's volume exactly."""

	def test_every_chart_point_returns_its_exact_volume(self) -> None:
		"""TC-PBT-004: interpolation at an exact chart row returns the chart value, not an approximation.

		This guards against floating-point drift in the interpolation formula.
		100 random strictly increasing charts, 2-12 rows each.
		"""
		rng = random.Random(SEED + 7)
		for run in range(RUNS):
			n = rng.randint(2, 12)
			depths = sorted({round(rng.uniform(0, 5000), 1) for _ in range(n * 2)})[:n]
			if len(depths) < 2:
				continue
			vols = [0.0]
			for _ in range(len(depths) - 1):
				vols.append(vols[-1] + rng.uniform(0.1, 500))
			rows = list(zip(depths, vols, strict=True))
			for depth, expected_vol in rows:
				got = interpolate(depth, rows)
				self.assertEqual(
					got,
					expected_vol,
					msg=f"run={run}: interpolate({depth}, ...) returned {got} not {expected_vol}",
				)

	def test_interpolation_between_exact_points_is_bounded(self) -> None:
		"""TC-PBT-004 corollary: an interpolated value is always between its two bracketing chart values."""
		rng = random.Random(SEED + 8)
		for run in range(RUNS):
			n = rng.randint(2, 10)
			depths = sorted({round(rng.uniform(0, 5000), 1) for _ in range(n * 2)})[:n]
			if len(depths) < 2:
				continue
			vols = [0.0]
			for _ in range(len(depths) - 1):
				vols.append(vols[-1] + rng.uniform(0.1, 500))
			rows = list(zip(depths, vols, strict=True))
			for i in range(len(rows) - 1):
				d0, v0 = rows[i]
				d1, v1 = rows[i + 1]
				mid_depth = (d0 + d1) / 2
				mid_vol = interpolate(mid_depth, rows)
				self.assertGreaterEqual(mid_vol, v0 - 1e-9, msg=f"run={run}")
				self.assertLessEqual(mid_vol, v1 + 1e-9, msg=f"run={run}")


class TestDriftSymmetryProperty(unittest.TestCase):
	"""TC-PBT-003 drift part: drift(A, B) = -drift(B, A) for all meter pairs."""

	def test_evol_vs_mvol_drift_is_antisymmetric(self) -> None:
		"""Drift A-B must equal the negation of drift B-A for 100 random meter pairs."""
		from forecourt.calc.drift import evol_vs_mvol

		rng = random.Random(SEED + 9)
		for _ in range(RUNS):
			a = rng.uniform(0, 10000)
			b = rng.uniform(0, 10000)
			self.assertAlmostEqual(evol_vs_mvol(a, b), -evol_vs_mvol(b, a), places=9)

	def test_within_tolerance_is_symmetric_around_zero(self) -> None:
		"""within_tolerance(d, sales) == within_tolerance(-d, sales) for all d and sales."""
		rng = random.Random(SEED + 10)
		for _ in range(RUNS):
			drift = rng.uniform(-500, 500)
			sales = rng.uniform(0, 50000)
			self.assertEqual(
				drift_ok(drift, sales),
				drift_ok(-drift, sales),
			)


if __name__ == "__main__":
	unittest.main()
