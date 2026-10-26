from frappe.tests.utils import FrappeTestCase

from forecourt.calc.calibration import interpolate, validate_rows


class TestCalibrationCalc(FrappeTestCase):
	def _rows(self) -> list[tuple[float, float]]:
		return [(0.0, 0.0), (100.0, 500.0), (200.0, 1100.0), (300.0, 1800.0)]

	def test_interpolate_exact(self):
		self.assertAlmostEqual(interpolate(100.0, self._rows()), 500.0)

	def test_interpolate_midpoint(self):
		result = interpolate(150.0, self._rows())
		self.assertAlmostEqual(result, 800.0)

	def test_interpolate_at_zero(self):
		self.assertAlmostEqual(interpolate(0.0, self._rows()), 0.0)

	def test_interpolate_at_max(self):
		self.assertAlmostEqual(interpolate(300.0, self._rows()), 1800.0)

	def test_interpolate_below_min_raises(self):
		with self.assertRaises(ValueError):
			interpolate(-1.0, self._rows())

	def test_interpolate_above_max_raises(self):
		with self.assertRaises(ValueError):
			interpolate(400.0, self._rows())

	def test_interpolate_empty_raises(self):
		with self.assertRaises(ValueError):
			interpolate(100.0, [])

	def test_validate_rows_ok(self):
		self.assertEqual(validate_rows(self._rows()), [])

	def test_validate_rows_non_increasing_depth(self):
		errors = validate_rows([(0.0, 0.0), (100.0, 500.0), (90.0, 600.0)])
		self.assertTrue(any("depth" in e for e in errors))

	def test_validate_rows_non_increasing_volume(self):
		errors = validate_rows([(0.0, 0.0), (100.0, 500.0), (200.0, 400.0)])
		self.assertTrue(any("volume" in e for e in errors))

	def test_validate_rows_too_short(self):
		errors = validate_rows([(0.0, 0.0)])
		self.assertTrue(errors)

	def test_validate_rows_two_rows_ok(self):
		self.assertEqual(validate_rows([(0.0, 0.0), (100.0, 500.0)]), [])
