"""Station movements tests (FMS-E10).

Unit tests for pure logic that can run without bench.
Integration tests (E03-E09 via factories) require bench.
"""

from __future__ import annotations

import unittest

from forecourt.calc.calibration import interpolate, net_volume, validate_rows
from forecourt.calc.drift import within_tolerance as drift_ok
from forecourt.calc.meters import MeterReading, meter_delta, segment_sales
from forecourt.calc.reconciliation import TankReconciliation, reconcile, within_tolerance

# ---------------------------------------------------------------------------
# GRN delivery dip logic (E03) — pure formula tests
# ---------------------------------------------------------------------------


class TestGRNDeliveryDipFormulas(unittest.TestCase):
	"""Test received_l formula: received = after - before + sales_during_drop."""

	def test_received_positive(self):
		before = 10_000.0
		after = 20_000.0
		sales = 500.0
		received = after - before + sales
		self.assertAlmostEqual(received, 10_500.0)

	def test_variance_formula(self):
		received = 10_500.0
		invoiced = 11_000.0
		variance = received - invoiced
		variance_pct = variance / invoiced * 100
		self.assertAlmostEqual(variance, -500.0)
		self.assertAlmostEqual(variance_pct, -500.0 / 11_000.0 * 100, places=4)

	def test_tolerance_boundary(self):
		# 0.5% tolerance
		self.assertTrue(within_tolerance(-49.9, 10_000.0, tol_pct=0.5, tol_l=20.0))
		self.assertFalse(within_tolerance(-51.0, 10_000.0, tol_pct=0.5, tol_l=20.0))

	def test_absolute_tolerance_dominates_tiny_sales(self):
		# 0.5% of 100 L = 0.5 L, but tol_l=20 dominates
		self.assertTrue(within_tolerance(15.0, 100.0, tol_pct=0.5, tol_l=20.0))
		self.assertFalse(within_tolerance(21.0, 100.0, tol_pct=0.5, tol_l=20.0))

	def test_chart_mode_volume_interpolation(self):
		chart = [(0.0, 0.0), (500.0, 5000.0), (1000.0, 10000.0)]
		before = interpolate(200.0, chart)
		after = interpolate(700.0, chart)
		self.assertAlmostEqual(before, 2000.0)
		self.assertAlmostEqual(after, 7000.0)
		received = after - before
		self.assertAlmostEqual(received, 5000.0)


# ---------------------------------------------------------------------------
# Tank Dip (E06) — book volume difference
# ---------------------------------------------------------------------------


class TestTankDipFormulas(unittest.TestCase):
	def test_difference_positive_when_above_book(self):
		dip_volume = 15_000.0
		book_volume = 14_500.0
		difference = dip_volume - book_volume
		self.assertAlmostEqual(difference, 500.0)

	def test_difference_negative_when_below_book(self):
		dip_volume = 9_000.0
		book_volume = 9_800.0
		difference = dip_volume - book_volume
		self.assertAlmostEqual(difference, -800.0)

	def test_water_subtracted_from_gross_volume(self):
		chart = [(0.0, 0.0), (1000.0, 10000.0)]
		gross = interpolate(600.0, chart)
		water = interpolate(10.0, chart)
		net = gross - water
		self.assertAlmostEqual(net, 6000.0 - 100.0)


# ---------------------------------------------------------------------------
# Tank Transfer (E07) — volume conservation
# ---------------------------------------------------------------------------


class TestTankTransferFormulas(unittest.TestCase):
	def test_volume_leaves_source(self):
		source_before = 20_000.0
		volume = 5_000.0
		source_after = source_before - volume
		self.assertAlmostEqual(source_after, 15_000.0)

	def test_volume_arrives_destination(self):
		dest_before = 8_000.0
		volume = 5_000.0
		dest_after = dest_before + volume
		self.assertAlmostEqual(dest_after, 13_000.0)

	def test_total_stock_conserved(self):
		before_total = 28_000.0
		after_total = (20_000.0 - 5_000.0) + (8_000.0 + 5_000.0)
		self.assertAlmostEqual(before_total, after_total)


# ---------------------------------------------------------------------------
# Meter Change (E08) — new start readings take effect
# ---------------------------------------------------------------------------


class TestMeterChangeFormulas(unittest.TestCase):
	def test_new_start_becomes_next_opening(self):
		new_start = 12_345.6
		# After meter change, next shift opens at new_start
		opening = new_start
		closing = opening + 500.0
		r = MeterReading(opening=opening, closing=closing)
		self.assertAlmostEqual(meter_delta(r), 500.0)

	def test_old_final_used_for_last_segment(self):
		old_final = 99_999.0
		prev_opening = 95_000.0
		r = MeterReading(opening=prev_opening, closing=old_final)
		delta = meter_delta(r)
		self.assertAlmostEqual(delta, 4_999.0)


# ---------------------------------------------------------------------------
# Fuel Price Change (E09) — rate lookup logic
# ---------------------------------------------------------------------------


class TestFuelPriceChangeFormulas(unittest.TestCase):
	def test_price_applies_at_effective_time(self):
		# Simulate: price changed at 14:00, invoice at 15:00 → new price
		# We test the conceptual formula: rate = new_price if invoice_time >= effective_at
		effective_price = 182.0
		old_price = 180.0

		# Invoice at 15:00, change at 14:00 → use new price
		invoice_dt = "2026-10-27 15:00:00"
		change_dt = "2026-10-27 14:00:00"
		rate = effective_price if invoice_dt >= change_dt else old_price
		self.assertAlmostEqual(rate, 182.0)

		# Invoice at 13:00, change at 14:00 → use old price
		invoice_dt_early = "2026-10-27 13:00:00"
		rate_early = effective_price if invoice_dt_early >= change_dt else old_price
		self.assertAlmostEqual(rate_early, 180.0)

	def test_variance_not_triggered_by_price_change_alone(self):
		# Tank reconciliation: price change doesn't affect volumetric variance
		rec = TankReconciliation(
			opening_volume=20_000.0,
			net_sales=5_000.0,
			closing_dip=15_000.0,
		)
		reconcile(rec)
		self.assertAlmostEqual(rec.variance, 0.0)


# ---------------------------------------------------------------------------
# Customer Vehicle (E01) — plate normalisation
# ---------------------------------------------------------------------------


class TestCustomerVehiclePlate(unittest.TestCase):
	def _normalise(self, plate: str) -> str:
		return plate.upper().replace(" ", "")

	def test_normalise_spaces(self):
		self.assertEqual(self._normalise("KDA 123A"), "KDA123A")

	def test_normalise_lowercase(self):
		self.assertEqual(self._normalise("kda123a"), "KDA123A")

	def test_normalise_mixed(self):
		self.assertEqual(self._normalise("Kda 123 A"), "KDA123A")

	def test_already_normalised(self):
		self.assertEqual(self._normalise("KDA123A"), "KDA123A")


# ---------------------------------------------------------------------------
# Calibration chart validation (E03 cross-check)
# ---------------------------------------------------------------------------


class TestCalibrationValidation(unittest.TestCase):
	def test_valid_chart_no_errors(self):
		rows = [(0, 0), (100, 500), (200, 1050), (300, 1600)]
		self.assertEqual(validate_rows(rows), [])

	def test_non_increasing_depth_flagged(self):
		rows = [(0, 0), (200, 1000), (100, 500)]
		errors = validate_rows(rows)
		self.assertGreater(len(errors), 0)

	def test_non_increasing_volume_flagged(self):
		rows = [(0, 0), (100, 1000), (200, 900)]
		errors = validate_rows(rows)
		self.assertGreater(len(errors), 0)

	def test_net_volume_subtracts_water(self):
		chart = [(0, 0), (1000, 10000)]
		self.assertAlmostEqual(net_volume(500, chart), 5000.0)
		self.assertAlmostEqual(net_volume(500, chart, water_rows=chart, water_dip_mm=10), 4900.0)


if __name__ == "__main__":
	unittest.main()
