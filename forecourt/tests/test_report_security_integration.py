"""Integration permission tests for FMS reports — FMS-SEC-001.

Verifies that report functions enforce station-level User Permissions
against REAL database data on the test site.  Tests create a restricted
user, assign User Permissions for one station only, and confirm that
the other station's data is completely invisible to that user.

These complement the mocked unit tests in test_report_security.py by
exercising the full call chain: User Permission → permitted_stations()
→ apply_station_permission() → frappe.get_all() filter → result rows.
"""

from __future__ import annotations

import frappe
from frappe.tests.classes import IntegrationTestCase

_RESTRICTED_USER = "test_sec_restricted@forecourt.example"
_STATION_A = "KE-NBO-ALPHA"
_STATION_B = "KE-NBO-BRAVO"


def _ensure_user() -> None:
	if frappe.db.exists("User", _RESTRICTED_USER):
		return
	frappe.get_doc(
		{
			"doctype": "User",
			"email": _RESTRICTED_USER,
			"first_name": "Security",
			"last_name": "Test",
			"enabled": 1,
			"new_password": "TestPass123!",
		}
	).insert(ignore_permissions=True)


def _set_station_permission(station: str | None) -> None:
	"""Replace all Station User Permissions for _RESTRICTED_USER."""
	frappe.db.delete("User Permission", {"user": _RESTRICTED_USER, "allow": "Station"})
	if station:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": _RESTRICTED_USER,
				"allow": "Station",
				"for_value": station,
			}
		).insert(ignore_permissions=True)


def _run_as(user: str, fn, *args, **kwargs):
	old = frappe.session.user
	frappe.set_user(user)
	try:
		return fn(*args, **kwargs)
	finally:
		frappe.set_user(old)


def _stations_in(rows: list[dict], key: str = "station") -> set[str]:
	return {r.get(key) or "" for r in rows} - {""}


class TestReportPermissionIntegration(IntegrationTestCase):
	"""Integration tests: real DB, real User Permissions, real query filters."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Only run if both stations and their data exist
		cls.has_data = (
			frappe.db.exists("Station", _STATION_A)
			and frappe.db.exists("Station", _STATION_B)
			and frappe.db.count("Sales Ledger Entry", {"station": _STATION_A, "is_cancelled": 0}) > 0
			and frappe.db.count("Sales Ledger Entry", {"station": _STATION_B, "is_cancelled": 0}) > 0
		)
		if cls.has_data:
			_ensure_user()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("User Permission", {"user": _RESTRICTED_USER, "allow": "Station"})
		super().tearDownClass()

	def _skip_if_no_data(self):
		if not self.has_data:
			self.skipTest(f"Skipped: test site lacks data in both {_STATION_A} and {_STATION_B}")

	# ------------------------------------------------------------------
	# sales_by_product
	# ------------------------------------------------------------------

	def test_sales_by_product_restricted_user_sees_only_permitted_station(self):
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		stations = _stations_in(rows)
		self.assertIn(_STATION_A, stations, "Permitted station absent from results")
		self.assertNotIn(_STATION_B, stations, f"Restricted station {_STATION_B} visible in results")

	def test_sales_by_product_cross_station_filter_blocked(self):
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {"station": _STATION_B})

		self.assertEqual(rows, [], f"Cross-station filter returned {len(rows)} rows, expected 0")

	def test_sales_by_product_permitted_alpha_cannot_see_bravo_in_unrestricted_query(self):
		"""With UP for ALPHA only, an unfiltered query must not contain BRAVO rows.

		This is the core multi-station enforcement check: the report aggregates
		across all stations the user is permitted for, and no row from a
		non-permitted station must appear even when no station filter is supplied.
		"""
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		for row in rows:
			self.assertNotEqual(
				row.get("station"),
				_STATION_B,
				f"BRAVO row appeared with no station filter for ALPHA-only user: {row}",
			)

	def test_sales_by_product_admin_sees_all_stations(self):
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.sales_by_product.sales_by_product import _data

		rows = _run_as("Administrator", _data, {})
		stations = _stations_in(rows)

		self.assertIn(_STATION_A, stations, "Admin cannot see STATION_A")
		self.assertIn(_STATION_B, stations, "Admin cannot see STATION_B")

	# ------------------------------------------------------------------
	# cash_collection (Cashier Ledger Entry)
	# ------------------------------------------------------------------

	def test_cash_collection_restricted_user_blocked(self):
		self._skip_if_no_data()
		if frappe.db.count("Cashier Ledger Entry", {"station": _STATION_B, "is_cancelled": 0}) == 0:
			self.skipTest("No CLE data for STATION_B")
		from forecourt.forecourt_finance.report.cash_collection.cash_collection import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		self.assertNotIn(_STATION_B, _stations_in(rows), f"{_STATION_B} data visible to restricted user")

	# ------------------------------------------------------------------
	# wetstock_variance (Wetstock Ledger Entry)
	# ------------------------------------------------------------------

	def test_wetstock_variance_restricted_user_blocked(self):
		self._skip_if_no_data()
		if frappe.db.count("Wetstock Ledger Entry", {"station": _STATION_B, "is_cancelled": 0}) == 0:
			self.skipTest("No WLE data for STATION_B")
		from forecourt.wetstock.report.wetstock_variance.wetstock_variance import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		self.assertNotIn(_STATION_B, _stations_in(rows), f"{_STATION_B} wetstock visible to restricted user")

	# ------------------------------------------------------------------
	# clearing_account_ageing (Payment Entry via fms_forecourt_shift subquery)
	# ------------------------------------------------------------------

	def test_clearing_account_ageing_restricted_user_blocked(self):
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.clearing_account_ageing.clearing_account_ageing import _data

		_set_station_permission(_STATION_A)
		# Cannot easily check by station (PE has no station field) — verify it
		# doesn't raise and returns a list (structural test only if no uncleared PEs exist)
		rows = _run_as(_RESTRICTED_USER, _data, {})
		self.assertIsInstance(rows, list)

	# ------------------------------------------------------------------
	# cash_position_by_station (Station DocType, name-based scoping)
	# ------------------------------------------------------------------

	def test_cash_position_by_station_restricted_user(self):
		self._skip_if_no_data()
		from forecourt.forecourt_finance.report.cash_position_by_station.cash_position_by_station import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		stations = _stations_in(rows)
		self.assertNotIn(_STATION_B, stations, f"{_STATION_B} visible in cash position for restricted user")

	# ------------------------------------------------------------------
	# fms_health (post-filter approach)
	# ------------------------------------------------------------------

	def test_fms_health_restricted_user_post_filtered(self):
		self._skip_if_no_data()
		from forecourt.forecourt_setup.report.fms_health.fms_health import _data

		_set_station_permission(_STATION_A)
		rows = _run_as(_RESTRICTED_USER, _data, {})

		for row in rows:
			st = row.get("station")
			if st is not None:
				self.assertNotEqual(
					st,
					_STATION_B,
					f"fms_health row for {_STATION_B} visible to restricted user",
				)
