"""Regression tests for run_out_forecast._forecast_row — Task C (FMS-R03).

Pure unit tests: no DB access, no Frappe site required.
"""

from __future__ import annotations

from frappe.tests.classes import UnitTestCase

from forecourt.wetstock.report.run_out_forecast.run_out_forecast import (
	_STATUS_FORECAST,
	_STATUS_NO_SALES,
	_STATUS_NO_STOCK,
	_forecast_row,
)


class TestForecastRow(UnitTestCase):
	def test_normal_forecast(self):
		row = _forecast_row(stock_l=1400.0, avg_daily=100.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_FORECAST)
		self.assertEqual(row["days_to_runout"], 14.0)
		self.assertEqual(row["runout_date"], "2026-01-15")

	def test_zero_avg_daily_has_stock(self):
		# Tank has stock but no recorded sales in lookback window.
		# Must NOT produce days=0 / runout=None silently — status makes it explicit.
		row = _forecast_row(stock_l=5000.0, avg_daily=0.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_NO_SALES)
		self.assertIsNone(row["days_to_runout"])
		self.assertIsNone(row["runout_date"])

	def test_negative_avg_daily_treated_as_no_sales(self):
		# Defensive: avg_daily should never be negative from the report,
		# but _forecast_row guards it anyway.
		row = _forecast_row(stock_l=5000.0, avg_daily=-1.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_NO_SALES)
		self.assertIsNone(row["days_to_runout"])

	def test_zero_stock_has_sales(self):
		row = _forecast_row(stock_l=0.0, avg_daily=100.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_NO_STOCK)
		self.assertEqual(row["days_to_runout"], 0.0)
		self.assertEqual(row["runout_date"], "2026-01-01")

	def test_zero_stock_no_sales(self):
		row = _forecast_row(stock_l=0.0, avg_daily=0.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_NO_STOCK)
		self.assertEqual(row["days_to_runout"], 0.0)

	def test_negative_stock_treated_as_no_stock(self):
		row = _forecast_row(stock_l=-50.0, avg_daily=100.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_NO_STOCK)

	def test_fractional_days(self):
		# 1500 L / 100 L/day = 15.0 days
		row = _forecast_row(stock_l=1500.0, avg_daily=100.0, as_of="2026-01-01")
		self.assertEqual(row["days_to_runout"], 15.0)
		self.assertEqual(row["runout_date"], "2026-01-16")

	def test_small_stock_rounds_down(self):
		# 50 L / 100 L/day = 0.5 → int(0.5) = 0 → runout same day
		row = _forecast_row(stock_l=50.0, avg_daily=100.0, as_of="2026-01-01")
		self.assertEqual(row["status"], _STATUS_FORECAST)
		self.assertEqual(row["days_to_runout"], 0.5)
		self.assertEqual(row["runout_date"], "2026-01-01")
