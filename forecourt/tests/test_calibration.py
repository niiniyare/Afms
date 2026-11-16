# Tests for FMS-D02: calibration interpolation
from __future__ import annotations

import unittest
from typing import ClassVar

from forecourt.calc.calibration import interpolate, net_volume, validate_rows

ROWS: list[tuple[float, float]] = [
	(0.0, 0.0),
	(100.0, 500.0),
	(200.0, 1200.0),
	(300.0, 2000.0),
]


class TestInterpolate(unittest.TestCase):
	def test_exact_match(self) -> None:
		self.assertEqual(interpolate(100.0, ROWS), 500.0)

	def test_midpoint(self) -> None:
		self.assertAlmostEqual(interpolate(150.0, ROWS), 850.0)

	def test_first_row(self) -> None:
		self.assertEqual(interpolate(0.0, ROWS), 0.0)

	def test_last_row(self) -> None:
		self.assertEqual(interpolate(300.0, ROWS), 2000.0)

	def test_below_min_raises(self) -> None:
		with self.assertRaises(ValueError):
			interpolate(-1.0, ROWS)

	def test_above_max_raises(self) -> None:
		with self.assertRaises(ValueError):
			interpolate(301.0, ROWS)

	def test_empty_raises(self) -> None:
		with self.assertRaises(ValueError):
			interpolate(100.0, [])

	def test_interpolation_accuracy(self) -> None:
		# 50 mm: between row 0 (0,0) and row 1 (100,500) → 250 L
		self.assertAlmostEqual(interpolate(50.0, ROWS), 250.0)


class TestValidateRows(unittest.TestCase):
	def test_valid(self) -> None:
		self.assertEqual(validate_rows(ROWS), [])

	def test_single_row(self) -> None:
		errors = validate_rows([(100.0, 500.0)])
		self.assertTrue(errors)

	def test_non_increasing_depth(self) -> None:
		bad = [(0.0, 0.0), (100.0, 500.0), (100.0, 600.0)]
		errors = validate_rows(bad)
		self.assertTrue(any("depth" in e.lower() for e in errors))

	def test_non_increasing_volume(self) -> None:
		bad = [(0.0, 0.0), (100.0, 500.0), (200.0, 400.0)]
		errors = validate_rows(bad)
		self.assertTrue(any("volume" in e.lower() for e in errors))


class TestNetVolume(unittest.TestCase):
	def test_no_water(self) -> None:
		self.assertAlmostEqual(net_volume(150.0, ROWS), 850.0)

	def test_with_water(self) -> None:
		water_rows: list[tuple[float, float]] = [
			(0.0, 0.0),
			(50.0, 100.0),
			(100.0, 250.0),
		]
		# product at 200 mm = 1200 L; water at 50 mm = 100 L; net = 1100 L
		result = net_volume(200.0, ROWS, water_rows=water_rows, water_dip_mm=50.0)
		self.assertAlmostEqual(result, 1100.0)

	def test_zero_water_dip(self) -> None:
		water_rows: list[tuple[float, float]] = [(0.0, 0.0), (100.0, 500.0)]
		result = net_volume(200.0, ROWS, water_rows=water_rows, water_dip_mm=0.0)
		self.assertAlmostEqual(result, 1200.0)

	def test_none_water_rows(self) -> None:
		self.assertAlmostEqual(net_volume(100.0, ROWS, water_rows=None), 500.0)


class TestInterpolateChartStartingAboveZero(unittest.TestCase):
	"""TC-CAL-033: chart whose minimum depth is above zero mm.

	The standard chart ROWS starts at 0 mm. Some tanks have a 'dead-band'
	and their chart starts at a higher depth (e.g. 50 mm). A measured dip
	below that minimum must be refused — the chart cannot extrapolate.
	"""

	ROWS_FROM_50: ClassVar[list[tuple[float, float]]] = [
		(50.0, 0.0),
		(150.0, 500.0),
		(250.0, 1200.0),
	]

	def test_depth_below_chart_minimum_raises_value_error(self) -> None:
		"""TC-CAL-033: depth 20 mm on a chart starting at 50 mm → ValueError naming the minimum."""
		with self.assertRaises(ValueError) as ctx:
			interpolate(20.0, self.ROWS_FROM_50)
		self.assertIn("50", str(ctx.exception))

	def test_depth_exactly_at_minimum_returns_first_row_value(self) -> None:
		"""TC-CAL-033: depth exactly at chart minimum is valid; returns first-row volume."""
		self.assertEqual(interpolate(50.0, self.ROWS_FROM_50), 0.0)

	def test_depth_between_rows_interpolates_correctly(self) -> None:
		"""TC-CAL-033: standard interpolation still works between rows above the minimum."""
		result = interpolate(100.0, self.ROWS_FROM_50)  # midpoint of [50,0] and [150,500]
		self.assertAlmostEqual(result, 250.0)


class TestWaterDepthExceedsProductDepth(unittest.TestCase):
	"""TC-CAL-036: impossible reading — water dip deeper than product dip.

	This can only happen if the sensor or the entry is wrong.
	The proposed behaviour (Q-06) is to raise ValueError.
	"""

	WATER_ROWS: ClassVar[list[tuple[float, float]]] = [
		(0.0, 0.0),
		(100.0, 300.0),
	]

	@unittest.skip("Q-06 open: proposed — refuse water dip > product dip depth")
	def test_water_dip_deeper_than_product_dip_raises_value_error(self) -> None:
		"""TC-CAL-036 (proposed): water_dip_mm 150 > product depth_mm 100 → ValueError.

		Current behaviour: returns a negative net volume (product_vol - water_vol < 0).
		Proposed: raise ValueError with a coded message so the dip entry is rejected.
		"""
		with self.assertRaises(ValueError):
			net_volume(100.0, ROWS, water_rows=self.WATER_ROWS, water_dip_mm=150.0)

	def test_current_behaviour_raises_when_water_dip_exceeds_water_chart_maximum(self) -> None:
		"""Documents actual current behaviour: when water_dip_mm exceeds the water chart's
		maximum depth, interpolate() raises ValueError (from the chart range check), which
		surfaces to the caller.

		Once Q-06 is resolved, the test above (marked skip) should replace this one.
		The expected final behaviour is an explicit ValueError with a business message
		naming both depths, not a chart-range error.
		"""
		with self.assertRaises(ValueError):
			net_volume(100.0, ROWS, water_rows=self.WATER_ROWS, water_dip_mm=150.0)


class TestValidateRowsEdgeCases(unittest.TestCase):
	"""TC-CAL-039 / TC-CAL-040 — chart validation helpers used by chart-import gate."""

	def test_chart_with_equal_depths_reports_error_naming_the_row(self) -> None:
		"""TC-MST-009: equal depths on two consecutive rows is invalid; error must name the row."""
		bad = [(0.0, 0.0), (100.0, 500.0), (100.0, 600.0)]
		errors = validate_rows(bad)
		self.assertTrue(errors)
		self.assertTrue(any("3" in e for e in errors), msg=f"Row number not in errors: {errors}")

	def test_chart_with_non_increasing_volume_reports_error(self) -> None:
		"""TC-MST-009: volume must be strictly increasing; flat or decreasing rows are invalid."""
		bad = [(0.0, 0.0), (100.0, 500.0), (200.0, 500.0)]  # equal volume
		errors = validate_rows(bad)
		self.assertTrue(errors)

	def test_valid_two_row_chart_accepted(self) -> None:
		"""Minimum valid chart: exactly two rows, both strictly increasing."""
		self.assertEqual(validate_rows([(0.0, 0.0), (100.0, 500.0)]), [])


if __name__ == "__main__":
	unittest.main()
