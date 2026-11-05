# Tests for FMS-D02: calibration interpolation
from __future__ import annotations

import unittest

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


if __name__ == "__main__":
	unittest.main()
