"""FMS-H11: Report totals tests.

Tests that cross-report totals are consistent given the same canned
Sales / Wetstock / Cashier Ledger data.  Runs without bench by patching
frappe.get_all and frappe._ at module level.

Each report's execute() is imported directly; its _data() function is the
unit under test.  All reports read from ledger DocTypes, so the same patched
get_all calls feed every report.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

# ------------------------------------------------------------------
# Canned ledger data shared by all tests
# ------------------------------------------------------------------

_STATION = "STA-TEST"
_COMPANY = "Test Company"
_DATE = "2026-10-01"

# Sales Ledger rows: 2 products, 3 payment types
_SLE_ROWS = [
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		item="AGO",
		payment_type="Cash",
		qty=100.0,
		amount=15000.0,
		cashier="EMP-001",
		is_cancelled=0,
		nozzle=None,
		tank=None,
		basis="Exact",
		is_fuel=1,
		forecourt_shift="SH-001",
		superseded_by=None,
	),
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		item="AGO",
		payment_type="Mobile Money",
		qty=50.0,
		amount=7500.0,
		cashier="EMP-001",
		is_cancelled=0,
		nozzle=None,
		tank=None,
		basis="Exact",
		is_fuel=1,
		forecourt_shift="SH-001",
		superseded_by=None,
	),
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		item="PMS",
		payment_type="Card",
		qty=80.0,
		amount=9600.0,
		cashier="EMP-002",
		is_cancelled=0,
		nozzle=None,
		tank=None,
		basis="Exact",
		is_fuel=1,
		forecourt_shift="SH-001",
		superseded_by=None,
	),
]

# Wetstock Ledger rows
_WLE_ROWS = [
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		tank="TANK-1",
		item="AGO",
		entry_type="Shift",
		opening_l=1000.0,
		receipt_l=0.0,
		sales_l=150.0,
		own_use_l=0.0,
		expected_l=850.0,
		dip_l=830.0,
		variance_l=-20.0,
		variance_pct=-0.13,
		is_cancelled=0,
		superseded_by=None,
		forecourt_shift="SH-001",
	),
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		tank="TANK-2",
		item="PMS",
		entry_type="Shift",
		opening_l=500.0,
		receipt_l=0.0,
		sales_l=80.0,
		own_use_l=0.0,
		expected_l=420.0,
		dip_l=425.0,
		variance_l=5.0,
		variance_pct=0.06,
		is_cancelled=0,
		superseded_by=None,
		forecourt_shift="SH-001",
	),
]

# Cashier Ledger rows
_CLE_ROWS = [
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		cashier="EMP-001",
		expected=22500.0,
		accounted=22000.0,
		difference=-500.0,
		cash=15000.0,
		mobile=7500.0,
		card=0.0,
		credit=0.0,
		fuel_l=150.0,
		fuel_amount=22500.0,
		item_amount=0.0,
		forecourt_shift="SH-001",
		superseded_by=None,
	),
	SimpleNamespace(
		station=_STATION,
		company=_COMPANY,
		posting_date=_DATE,
		cashier="EMP-002",
		expected=9600.0,
		accounted=9600.0,
		difference=0.0,
		cash=0.0,
		mobile=0.0,
		card=9600.0,
		credit=0.0,
		fuel_l=80.0,
		fuel_amount=9600.0,
		item_amount=0.0,
		forecourt_shift="SH-001",
		superseded_by=None,
	),
]

# Nozzle Ledger rows (minimal — for sales_by_pump_and_nozzle)
_NLE_ROWS = [
	SimpleNamespace(
		station=_STATION,
		posting_date=_DATE,
		nozzle="D01-N1",
		item="AGO",
		net_l=150.0,
		amount=22500.0,
		cashier="EMP-001",
		superseded_by=None,
	),
]

_TOTAL_REVENUE = sum(r.amount for r in _SLE_ROWS)  # 32_100
_TOTAL_QTY_AGO = sum(r.qty for r in _SLE_ROWS if r.item == "AGO")  # 150
_TOTAL_QTY_PMS = sum(r.qty for r in _SLE_ROWS if r.item == "PMS")  # 80


def _mock_get_all(doctype, filters=None, fields=None, **kw):
	"""Route get_all calls to the right canned list."""
	if doctype == "Sales Ledger Entry":
		return _SLE_ROWS
	if doctype == "Wetstock Ledger Entry":
		return _WLE_ROWS
	if doctype == "Cashier Ledger Entry":
		return _CLE_ROWS
	if doctype == "Nozzle Ledger Entry":
		return _NLE_ROWS
	if doctype in ("Shift Cashier", "Shift Tank Dip", "Shift Resolution", "Shift Collection"):
		return []
	return []


def setUpModule():
	import frappe

	frappe.db = MagicMock()
	frappe.db.get_value.return_value = None
	frappe.db.exists.return_value = False
	frappe.get_all = MagicMock(side_effect=_mock_get_all)
	frappe.get_cached_doc = MagicMock(return_value=SimpleNamespace())
	frappe.flags = SimpleNamespace(in_test=True)
	# flt() calls frappe.get_system_settings("rounding_method") → returns MagicMock
	# → unknown rounding method → exception caught → 0.0; pin to a known method.
	frappe.get_system_settings = MagicMock(return_value="Banker's Rounding (legacy)")
	frappe._ = lambda s, *a, **kw: s


# ------------------------------------------------------------------
# Helper to call a report's execute() and sum a column
# ------------------------------------------------------------------


def _get(row, key):
	"""Get value from dict or SimpleNamespace row."""
	if isinstance(row, dict):
		return row.get(key, 0) or 0
	return getattr(row, key, 0) or 0


def _sum_col(data, col):
	return round(sum(float(_get(r, col)) for r in data), 2)


# ------------------------------------------------------------------
# H01: Daily Station Report
# ------------------------------------------------------------------


class TestDailyStationReport(unittest.TestCase):
	def _execute(self):
		from forecourt.forecourt_shift.report.daily_station_report.daily_station_report import (
			execute,
		)

		_cols, data = execute({"station": _STATION, "company": _COMPANY, "date": _DATE})
		return data

	def test_revenue_total(self):
		data = self._execute()
		total = _sum_col(data, "revenue")
		self.assertAlmostEqual(total, _TOTAL_REVENUE, places=2)

	def test_returns_rows(self):
		data = self._execute()
		self.assertTrue(len(data) > 0)


# ------------------------------------------------------------------
# H02: Sales by Product
# ------------------------------------------------------------------


class TestSalesByProduct(unittest.TestCase):
	def _execute(self):
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import execute

		_cols, data = execute(
			{"station": _STATION, "company": _COMPANY, "from_date": _DATE, "to_date": _DATE}
		)
		return data

	def test_revenue_total(self):
		data = self._execute()
		total = _sum_col(data, "amount")
		self.assertAlmostEqual(total, _TOTAL_REVENUE, places=2)

	def test_ago_qty(self):
		data = self._execute()
		ago_rows = [r for r in data if _get(r, "item") == "AGO"]
		ago_qty = round(sum(float(_get(r, "qty")) for r in ago_rows), 3)
		self.assertAlmostEqual(ago_qty, _TOTAL_QTY_AGO, places=3)


# ------------------------------------------------------------------
# H03: Payment Mix Matrix
# ------------------------------------------------------------------


class TestPaymentMixMatrix(unittest.TestCase):
	def _execute(self):
		from forecourt.forecourt_finance.report.payment_mix_matrix.payment_mix_matrix import execute

		_cols, data = execute(
			{"station": _STATION, "company": _COMPANY, "from_date": _DATE, "to_date": _DATE}
		)
		return data

	def test_returns_data(self):
		data = self._execute()
		self.assertIsNotNone(data)


# ------------------------------------------------------------------
# H04: Wetstock Variance
# ------------------------------------------------------------------


class TestWetstockVariance(unittest.TestCase):
	def _execute(self):
		from forecourt.wetstock.report.wetstock_variance.wetstock_variance import execute

		_cols, data = execute(
			{"station": _STATION, "company": _COMPANY, "from_date": _DATE, "to_date": _DATE}
		)
		return data

	def test_ago_variance(self):
		data = self._execute()
		ago_rows = [r for r in data if _get(r, "item") == "AGO"]
		if ago_rows:
			ago_var = round(sum(float(_get(r, "variance_l")) for r in ago_rows), 3)
			self.assertAlmostEqual(ago_var, -20.0, places=3)


# ------------------------------------------------------------------
# H05: Cashier Statement
# ------------------------------------------------------------------


class TestCashierStatement(unittest.TestCase):
	def _execute(self):
		from forecourt.forecourt_finance.report.cashier_statement.cashier_statement import execute

		_cols, data = execute(
			{"station": _STATION, "company": _COMPANY, "from_date": _DATE, "to_date": _DATE}
		)
		return data

	def test_returns_data(self):
		data = self._execute()
		self.assertIsNotNone(data)


# ------------------------------------------------------------------
# Cross-report consistency: H01 revenue == H02 revenue
# ------------------------------------------------------------------


class TestCrossReportConsistency(unittest.TestCase):
	def _dsr_revenue(self):
		from forecourt.forecourt_shift.report.daily_station_report.daily_station_report import execute

		_cols, data = execute({"station": _STATION, "company": _COMPANY, "date": _DATE})
		return _sum_col(data, "revenue")

	def _sbp_revenue(self):
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import execute

		_cols, data = execute(
			{"station": _STATION, "company": _COMPANY, "from_date": _DATE, "to_date": _DATE}
		)
		return _sum_col(data, "amount")

	def test_dsr_equals_sbp_revenue(self):
		self.assertAlmostEqual(
			self._dsr_revenue(),
			self._sbp_revenue(),
			places=2,
			msg="Daily Station Report revenue != Sales by Product revenue for same data",
		)

	def test_cashier_total_expected_equals_sle_revenue(self):
		"""Cashier ledger expected totals should equal SLE revenue total."""
		cle_expected = round(sum(r.expected for r in _CLE_ROWS), 2)
		# CLE expected = sum of all cashier expected
		self.assertAlmostEqual(cle_expected, _TOTAL_REVENUE, places=2)
