"""Cross-station security regression tests — FMS-SEC-001.

Proves that every report respects station-level User Permissions:
  - A user permitted to STA-A only cannot retrieve STA-B data.
  - A user with no station permissions gets an empty result.
  - An unrestricted user (Director / Administrator) gets unfiltered results.

All tests are unit tests (no DB): frappe.get_all and get_permitted_stations
are mocked so the tests run without a live site.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from frappe.tests.classes import UnitTestCase

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_PERMITTED_PATCH = "forecourt.reports.common.get_permitted_stations"


def _mock_get_all(return_value=None):
	"""Return a MagicMock for frappe.get_all that returns return_value."""
	m = MagicMock(return_value=return_value or [])
	return m


def _station_in_filters(mock_get_all_calls: list) -> list | None:
	"""Extract the 'station' value from the first get_all call's filters kwarg."""
	for c in mock_get_all_calls:
		filters = c.kwargs.get("filters") or (c.args[1] if len(c.args) > 1 else {})
		if isinstance(filters, dict) and "station" in filters:
			return filters["station"]
	return None


def _shift_filter_in_calls(mock_get_all_calls: list) -> dict | None:
	"""Find the Payment Entry call and return its filters."""
	for c in mock_get_all_calls:
		doctype = c.args[0] if c.args else c.kwargs.get("doctype")
		if doctype == "Payment Entry":
			return c.kwargs.get("filters") or (c.args[1] if len(c.args) > 1 else {})
	return None


# ---------------------------------------------------------------------------
# apply_station_permission unit tests
# ---------------------------------------------------------------------------


class TestApplyStationPermission(UnitTestCase):
	"""Direct unit tests for the common helper."""

	def setUp(self):
		from forecourt.reports.common import apply_station_permission

		self._fn = apply_station_permission

	def test_restricted_user_no_filter_adds_station_in(self):
		with patch(_PERMITTED_PATCH, return_value=["STA-A"]):
			f = {"is_cancelled": 0}
			err = self._fn(f, {})
		self.assertIsNone(err)
		self.assertEqual(f["station"], ["in", ["STA-A"]])

	def test_restricted_user_matching_station_filter(self):
		with patch(_PERMITTED_PATCH, return_value=["STA-A"]):
			f = {"is_cancelled": 0}
			err = self._fn(f, {"station": "STA-A"})
		self.assertIsNone(err)
		self.assertEqual(f["station"], ["in", ["STA-A"]])

	def test_restricted_user_non_permitted_station_returns_error(self):
		with patch(_PERMITTED_PATCH, return_value=["STA-A"]):
			f = {"is_cancelled": 0}
			err = self._fn(f, {"station": "STA-B"})
		self.assertIsNotNone(err)
		self.assertIn("FMS-R902", err)

	def test_no_station_permission_returns_error(self):
		with patch(_PERMITTED_PATCH, return_value=[]):
			f = {"is_cancelled": 0}
			err = self._fn(f, {})
		self.assertIsNotNone(err)

	def test_unrestricted_user_no_station_filter(self):
		with patch(_PERMITTED_PATCH, return_value=None):
			f = {"is_cancelled": 0}
			err = self._fn(f, {})
		self.assertIsNone(err)
		self.assertNotIn("station", f)

	def test_unrestricted_user_with_station_filter(self):
		with patch(_PERMITTED_PATCH, return_value=None):
			f = {"is_cancelled": 0}
			err = self._fn(f, {"station": "STA-B"})
		self.assertIsNone(err)
		self.assertEqual(f["station"], ["in", ["STA-B"]])

	def test_company_filter_scopes_candidates(self):
		with patch(_PERMITTED_PATCH, return_value=["STA-A", "STA-C"]):
			with patch(
				"frappe.get_all",
				return_value=["STA-A", "STA-X"],
			):
				f = {"is_cancelled": 0}
				err = self._fn(f, {"company": "ACME"})
		self.assertIsNone(err)
		# Intersection: STA-A is both in permitted and in company stations
		self.assertIn("STA-A", f["station"][1])
		self.assertNotIn("STA-X", f["station"][1])


# ---------------------------------------------------------------------------
# CLE-based reports (cash_collection, cashier_statement, etc.)
# ---------------------------------------------------------------------------


class TestCashCollectionPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.cash_collection.cash_collection import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_user_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_stations_returns_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_unrestricted_user_no_station_filter(self):
		_, m = self._call(None)
		f = _station_in_filters(m.call_args_list)
		self.assertIsNone(f)

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


class TestCashierStatementPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.cashier_statement.cashier_statement import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_user_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_returns_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# SLE-based reports
# ---------------------------------------------------------------------------


class TestSalesByProductPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_user_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_returns_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])

	def test_unrestricted_no_station_in_query(self):
		_, m = self._call(None)
		f = _station_in_filters(m.call_args_list)
		self.assertIsNone(f)


class TestSalesByShiftPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_shift.report.sales_by_shift.sales_by_shift import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# WLE / NLE based reports
# ---------------------------------------------------------------------------


class TestWetstockVariancePermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.wetstock.report.wetstock_variance.wetstock_variance import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


class TestTankStockMovementPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.wetstock.report.tank_stock_movement.tank_stock_movement import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])


class TestMeterDriftPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.wetstock.report.meter_drift.meter_drift import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Forecourt Shift based reports
# ---------------------------------------------------------------------------


class TestExceptionRegisterPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_shift.report.exception_register.exception_register import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_shift_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


class TestCreditSlipsRegisterPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.credit_slips_register.credit_slips_register import (
			_data,
		)

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_shift_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Multi-dict: station_comparison
# ---------------------------------------------------------------------------


class TestStationComparisonPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.station_comparison.station_comparison import _data

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])

	def test_unrestricted_no_station_in_query(self):
		_, m = self._call(None)
		f = _station_in_filters(m.call_args_list)
		self.assertIsNone(f)


# ---------------------------------------------------------------------------
# Special case: clearing_account_ageing (subquery via fms_forecourt_shift)
# ---------------------------------------------------------------------------


class TestClearingAccountAgeingPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from frappe.utils import today

		from forecourt.forecourt_finance.report.clearing_account_ageing.clearing_account_ageing import (
			_data,
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Forecourt Shift":
				return ["SH-001", "SH-002"] if permitted else []
			return []

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", side_effect=fake_get_all) as m:
				result = _data(filters or {"date": today()})
		return result, m

	def test_restricted_user_shift_subquery_applied(self):
		_, m = self._call(["STA-A"])
		# Payment Entry call should have fms_forecourt_shift filter
		pe_filters = _shift_filter_in_calls(m.call_args_list)
		self.assertIsNotNone(pe_filters)
		self.assertIn("fms_forecourt_shift", pe_filters)

	def test_no_permitted_returns_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_unrestricted_no_shift_subquery(self):
		_, m = self._call(None)
		pe_filters = _shift_filter_in_calls(m.call_args_list)
		if pe_filters:
			self.assertNotIn("fms_forecourt_shift", pe_filters)


# ---------------------------------------------------------------------------
# Special case: cash_position_by_station (Station DocType)
# ---------------------------------------------------------------------------


class TestCashPositionByStationPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from frappe.utils import today

		from forecourt.forecourt_finance.report.cash_position_by_station.cash_position_by_station import (
			_data,
		)

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {"date": today()})
		return result, m

	def test_restricted_station_name_filter_applied(self):
		_, m = self._call(["STA-A"])
		# Check the Station query filters
		for c in m.call_args_list:
			dt = c.args[0] if c.args else c.kwargs.get("doctype")
			if dt == "Station":
				f = c.kwargs.get("filters") or (c.args[1] if len(c.args) > 1 else {})
				self.assertEqual(f.get("name"), ["in", ["STA-A"]])
				return
		self.fail("No Station query found")

	def test_no_permitted_returns_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])

	def test_permitted_station_matches_filter(self):
		_, m = self._call(["STA-A"], {"station": "STA-A"})
		for c in m.call_args_list:
			dt = c.args[0] if c.args else c.kwargs.get("doctype")
			if dt == "Station":
				f = c.kwargs.get("filters") or (c.args[1] if len(c.args) > 1 else {})
				self.assertEqual(f.get("name"), "STA-A")
				return


# ---------------------------------------------------------------------------
# Special case: payment_reconciliation (Payment Feed Entry has station field)
# ---------------------------------------------------------------------------


class TestPaymentReconciliationPermissions(UnitTestCase):
	def _call(self, permitted, filters=None):
		from forecourt.forecourt_finance.report.payment_reconciliation.payment_reconciliation import (
			_data,
		)

		with patch(_PERMITTED_PATCH, return_value=permitted):
			with patch("frappe.get_all", return_value=[]) as m:
				result = _data(filters or {})
		return result, m

	def test_restricted_station_filter_applied(self):
		_, m = self._call(["STA-A"])
		f = _station_in_filters(m.call_args_list)
		self.assertEqual(f, ["in", ["STA-A"]])

	def test_no_permitted_empty(self):
		result, _ = self._call([])
		self.assertEqual(result, [])

	def test_cross_station_blocked(self):
		result, _ = self._call(["STA-A"], {"station": "STA-B"})
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# fms_health: post-filter removes unauthorised stations
# ---------------------------------------------------------------------------


class TestFmsHealthPermissions(UnitTestCase):
	def test_no_permitted_returns_empty(self):
		from forecourt.forecourt_setup.report.fms_health.fms_health import _data

		with patch(_PERMITTED_PATCH, return_value=[]):
			result = _data({})
		self.assertEqual(result, [])

	def test_cross_station_request_blocked(self):
		from forecourt.forecourt_setup.report.fms_health.fms_health import _data

		with patch(_PERMITTED_PATCH, return_value=["STA-A"]):
			with patch("frappe.db.table_exists", return_value=False):
				result = _data({"station": "STA-B"})
		self.assertEqual(result, [])

	def test_post_filter_removes_unauthorised_station_rows(self):
		"""Rows from sub-checks for STA-B must not appear for STA-A user."""
		from forecourt.forecourt_setup.report.fms_health.fms_health import _data

		fake_rows = [
			{
				"category": "No Recent Shift",
				"station": "STA-A",
				"issue": "...",
				"age_days": 1,
				"document": "STA-A",
				"doctype": "Station",
			},
			{
				"category": "No Recent Shift",
				"station": "STA-B",
				"issue": "...",
				"age_days": 1,
				"document": "STA-B",
				"doctype": "Station",
			},
			{
				"category": "Failed Integration",
				"station": None,
				"issue": "...",
				"age_days": 0,
				"document": "INB-001",
				"doctype": "Integration Inbox",
			},
		]

		with patch(_PERMITTED_PATCH, return_value=["STA-A"]):
			with patch(
				"forecourt.forecourt_setup.report.fms_health.fms_health._check_no_shift_today",
				return_value=fake_rows,
			):
				with patch(
					"forecourt.forecourt_setup.report.fms_health.fms_health._check_stale_draft_shifts",
					return_value=[],
				):
					with patch(
						"forecourt.forecourt_setup.report.fms_health.fms_health._check_stale_nozzle_readings",
						return_value=[],
					):
						with patch(
							"forecourt.forecourt_setup.report.fms_health.fms_health._check_tank_stock",
							return_value=[],
						):
							with patch(
								"forecourt.forecourt_setup.report.fms_health.fms_health._check_old_clearing_items",
								return_value=[],
							):
								with patch(
									"forecourt.forecourt_setup.report.fms_health.fms_health._check_failed_inbox",
									return_value=[],
								):
									with patch(
										"forecourt.forecourt_setup.report.fms_health.fms_health._check_calibration_charts",
										return_value=[],
									):
										result = _data({})

		stations_in_result = [r["station"] for r in result]
		self.assertIn("STA-A", stations_in_result)
		self.assertNotIn("STA-B", stations_in_result)
		self.assertIn(None, stations_in_result)  # Integration Inbox row passes through


# ---------------------------------------------------------------------------
# apply_date_filter and apply_shift_date_filter unit tests (FMS-R03)
# ---------------------------------------------------------------------------


class TestApplyDateFilter(UnitTestCase):
	"""Tests for the two date-range filter helpers in common.py."""

	def setUp(self):
		from forecourt.reports.common import apply_date_filter, apply_shift_date_filter

		self._adf = apply_date_filter
		self._asdf = apply_shift_date_filter

	# --- apply_date_filter ---

	def test_both_dates_produces_between(self):
		f: dict = {}
		self._adf(f, {"from_date": "2026-01-01", "to_date": "2026-01-31"})
		self.assertEqual(f["posting_date"], ["between", ["2026-01-01", "2026-01-31"]])

	def test_only_from_date(self):
		f: dict = {}
		self._adf(f, {"from_date": "2026-01-01"})
		self.assertEqual(f["posting_date"], [">=", "2026-01-01"])

	def test_only_to_date(self):
		f: dict = {}
		self._adf(f, {"to_date": "2026-01-31"})
		self.assertEqual(f["posting_date"], ["<=", "2026-01-31"])

	def test_no_dates_no_mutation(self):
		f: dict = {"is_cancelled": 0}
		self._adf(f, {})
		self.assertNotIn("posting_date", f)
		self.assertEqual(f, {"is_cancelled": 0})

	def test_custom_date_field(self):
		f: dict = {}
		self._adf(f, {"from_date": "2026-03-01", "to_date": "2026-03-31"}, date_field="transaction_date")
		self.assertEqual(f["transaction_date"], ["between", ["2026-03-01", "2026-03-31"]])

	def test_does_not_add_posting_date_when_custom_field_used(self):
		f: dict = {}
		self._adf(f, {"from_date": "2026-01-01"}, date_field="shift_date")
		self.assertNotIn("posting_date", f)
		self.assertIn("shift_date", f)

	# --- apply_shift_date_filter ---

	def test_shift_both_dates(self):
		f: dict = {}
		self._asdf(f, {"from_date": "2026-02-01", "to_date": "2026-02-28"})
		self.assertEqual(f["shift_date"], ["between", ["2026-02-01", "2026-02-28"]])

	def test_shift_only_from_date(self):
		f: dict = {}
		self._asdf(f, {"from_date": "2026-02-01"})
		self.assertEqual(f["shift_date"], [">=", "2026-02-01"])

	def test_shift_no_dates_no_mutation(self):
		f: dict = {"docstatus": 1}
		self._asdf(f, {})
		self.assertNotIn("shift_date", f)

	def test_shift_does_not_set_posting_date(self):
		f: dict = {}
		self._asdf(f, {"from_date": "2026-01-01", "to_date": "2026-01-31"})
		self.assertNotIn("posting_date", f)


# ---------------------------------------------------------------------------
# validate_date_range unit tests (FMS-R03)
# ---------------------------------------------------------------------------


class TestValidateDateRange(UnitTestCase):
	def setUp(self):
		from forecourt.reports.common import validate_date_range

		self._fn = validate_date_range

	def test_valid_range_returns_none(self):
		result = self._fn("2026-01-01", "2026-01-31")
		self.assertIsNone(result)

	def test_inverted_dates_returns_r801(self):
		result = self._fn("2026-01-31", "2026-01-01")
		self.assertIsNotNone(result)
		self.assertIn("FMS-R801", result)

	def test_range_exceeding_max_returns_r802(self):
		result = self._fn("2024-01-01", "2026-01-01", max_days=366)
		self.assertIsNotNone(result)
		self.assertIn("FMS-R802", result)

	def test_range_exactly_at_max_is_valid(self):
		result = self._fn("2026-01-01", "2026-01-01", max_days=1)
		self.assertIsNone(result)

	def test_missing_from_date_returns_none(self):
		result = self._fn(None, "2026-01-31")
		self.assertIsNone(result)

	def test_missing_to_date_returns_none(self):
		result = self._fn("2026-01-01", None)
		self.assertIsNone(result)

	def test_both_missing_returns_none(self):
		result = self._fn(None, None)
		self.assertIsNone(result)
