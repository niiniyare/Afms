from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


def _company() -> str:
	return (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", limit=1, pluck="name")[0]
	)


def _abbr(company: str) -> str:
	return frappe.get_cached_value("Company", company, "abbr")


def _cash_account(company: str) -> str | None:
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Cash", "is_group": 0},
		"name",
	)


def _cost_center(company: str) -> str | None:
	return frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 0},
		"name",
	)


def _currency(company: str) -> str:
	return frappe.get_cached_value("Company", company, "default_currency") or "USD"


def _warehouse_group(company: str) -> str | None:
	return frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 1},
		"name",
	)


def _price_list() -> str | None:
	return frappe.db.get_value("Price List", {}, "name")


def _station_group() -> str | None:
	return frappe.db.get_value("Station Group", {}, "name")


class TestStation(FrappeTestCase):
	def setUp(self) -> None:
		self.company = _company()
		self.abbr = _abbr(self.company)
		self.cash_account = _cash_account(self.company)
		self.cost_center = _cost_center(self.company)
		self.warehouse_group = _warehouse_group(self.company)
		self.price_list = _price_list()
		self.station_group = _station_group()

	def tearDown(self) -> None:
		frappe.db.delete("Station", {"station_code": ["like", "TS-%"]})
		frappe.db.delete("Customer", {"customer_name": ["like", "Walk-in – _Test%"]})  # noqa: RUF001

	def _minimal_doc(self, code: str = "TS-NBO-ST1", **overrides) -> "frappe.Document":
		"""Build a minimally valid Station doc."""
		if not all(
			[
				self.cash_account,
				self.cost_center,
				self.warehouse_group,
				self.price_list,
				self.station_group,
			]
		):
			self.skipTest("Test site missing required master data.")
		data = {
			"doctype": "Station",
			"station_code": code,
			"station_name": "_Test Station",
			"company": self.company,
			"station_group": self.station_group,
			"country": frappe.db.get_value("Country", {}, "name"),
			"ownership_type": "Company-owned",
			"timezone": "UTC",
			"warehouse_group": self.warehouse_group,
			"price_list": self.price_list,
			"cost_center": self.cost_center,
			"safe_account": self.cash_account,
			"till_accounts": [
				{
					"currency": _currency(self.company),
					"account": self.cash_account,
				}
			],
		}
		data.update(overrides)
		return frappe.get_doc(data)

	# ------------------------------------------------------------------
	# FMS-M601: station code pattern
	# ------------------------------------------------------------------

	def test_code_valid(self) -> None:
		doc = self._minimal_doc("TS-NBO-WSTL")
		doc.validate()  # must not raise

	def test_code_lowercase_rejected(self) -> None:
		doc = self._minimal_doc("ke-nbo-wstl")
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M601"):
			doc.validate()

	def test_code_too_short_area_rejected(self) -> None:
		doc = self._minimal_doc("KE-N-WSTL")
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M601"):
			doc.validate()

	def test_code_too_long_site_rejected(self) -> None:
		doc = self._minimal_doc("KE-NBO-TOOLONGCODE")
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M601"):
			doc.validate()

	def test_code_with_digits_valid(self) -> None:
		doc = self._minimal_doc("KE-NB1-W2STL")
		doc.validate()  # must not raise

	# ------------------------------------------------------------------
	# FMS-M602: wrong company account / warehouse
	# ------------------------------------------------------------------

	def test_account_wrong_company_rejected(self) -> None:
		other = frappe.get_all(
			"Company",
			filters=[["name", "!=", self.company]],
			limit=1,
			pluck="name",
		)
		if not other:
			self.skipTest("Only one company in the test site.")
		other_account = frappe.db.get_value(
			"Account",
			{"company": other[0], "account_type": "Cash", "is_group": 0},
			"name",
		)
		if not other_account:
			self.skipTest("No cash account found for other company.")
		doc = self._minimal_doc(safe_account=other_account)
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M602"):
			doc.validate()

	def test_till_account_wrong_company_rejected(self) -> None:
		other = frappe.get_all(
			"Company",
			filters=[["name", "!=", self.company]],
			limit=1,
			pluck="name",
		)
		if not other:
			self.skipTest("Only one company in the test site.")
		other_account = frappe.db.get_value(
			"Account",
			{"company": other[0], "account_type": "Cash", "is_group": 0},
			"name",
		)
		if not other_account:
			self.skipTest("No cash account for other company.")
		doc = self._minimal_doc(
			till_accounts=[{"currency": _currency(self.company), "account": other_account}]
		)
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M602"):
			doc.validate()

	# ------------------------------------------------------------------
	# FMS-M603: meter override consistency
	# ------------------------------------------------------------------

	def test_meters_use_settings_skips_check(self) -> None:
		doc = self._minimal_doc()
		doc.use_settings_meters = 1
		doc.sales_basis = "Elec Cash"
		doc.record_elec_cash = 0
		doc.validate()  # must not raise — global settings used

	def test_meter_basis_without_meter_rejected(self) -> None:
		doc = self._minimal_doc()
		doc.use_settings_meters = 0
		doc.sales_basis = "Elec Cash"
		doc.record_elec_cash = 0
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M603"):
			doc.validate()

	def test_meter_basis_man_meter_ok(self) -> None:
		doc = self._minimal_doc()
		doc.use_settings_meters = 0
		doc.sales_basis = "Man Meter"
		doc.record_man_meter = 1
		doc.validate()  # must not raise

	def test_highest_needs_two_meters(self) -> None:
		doc = self._minimal_doc()
		doc.use_settings_meters = 0
		doc.sales_basis = "Highest"
		doc.record_elec_cash = 1
		doc.record_elec_meter = 0
		doc.record_man_meter = 0
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M603"):
			doc.validate()

	def test_highest_with_two_meters_ok(self) -> None:
		doc = self._minimal_doc()
		doc.use_settings_meters = 0
		doc.sales_basis = "Highest"
		doc.record_elec_cash = 1
		doc.record_elec_meter = 1
		doc.validate()  # must not raise

	# ------------------------------------------------------------------
	# after_insert: walk-in customer created
	# ------------------------------------------------------------------

	def test_walk_in_customer_created_on_insert(self) -> None:
		doc = self._minimal_doc("TS-WLK-ST1")
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertTrue(doc.walk_in_customer, "walk_in_customer not set after insert")
		self.assertTrue(
			frappe.db.exists("Customer", doc.walk_in_customer),
			"Walk-in customer record not found",
		)

	def test_walk_in_customer_name_matches_station_name(self) -> None:
		doc = self._minimal_doc("TS-WLK-ST2", station_name="_Test Walkin Station")
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.walk_in_customer, "Walk-in – _Test Walkin Station")  # noqa: RUF001

	def test_walk_in_customer_has_fms_flags(self) -> None:
		doc = self._minimal_doc("TS-WLK-ST3")
		doc.insert(ignore_permissions=True)
		doc.reload()
		cust = frappe.get_doc("Customer", doc.walk_in_customer)
		self.assertEqual(cust.fms_is_walk_in, 1)
		self.assertEqual(cust.fms_station, doc.name)
