"""
Test factories for FMS integration tests.

Each function inserts a minimal valid record and returns the doc.
Tests that need different values pass overrides via kwargs.
Never leave persistent state — use FMSTestCase which rolls back.
"""

from __future__ import annotations

import frappe
import frappe.test_runner
from frappe.tests.utils import FrappeTestCase


def _ensure_test_company() -> str:
	"""Return a company name, loading ERPNext test records if none exist."""
	company = frappe.defaults.get_defaults().get("company")
	if company:
		return company
	companies = frappe.get_all("Company", limit=1, pluck="name")
	if companies:
		return companies[0]
	# No company on a fresh test site — load ERPNext's standard test records.
	# This is what bench run-tests --app erpnext does in its own setUpClass.
	frappe.test_runner.make_test_records("Company")
	companies = frappe.get_all("Company", limit=1, pluck="name")
	if companies:
		return companies[0]
	frappe.throw(frappe._("No company found. Run ERPNext setup before FMS tests."))


class FMSTestCase(FrappeTestCase):
	"""Base class for FMS integration tests. Rolls back after each test."""

	pass


def make_station_group(name: str = "KE", **kwargs) -> frappe.Document:
	if frappe.db.exists("Station Group", name):
		return frappe.get_doc("Station Group", name)
	doc = frappe.get_doc(
		{
			"doctype": "Station Group",
			"station_group_name": name,
			"group_type": "Other",
			"is_group": 1,
			"parent_station_group": None,
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def make_station(
	code: str = "KE-NBO-TEST",
	company: str | None = None,
	group: str | None = None,
	**kwargs,
) -> frappe.Document:
	if frappe.db.exists("Station", code):
		return frappe.get_doc("Station", code)
	if not company:
		company = _ensure_test_company()
	if not group:
		group = make_station_group().name
	abbr = frappe.db.get_value("Company", company, "abbr") or "TC"
	currency = frappe.db.get_value("Company", company, "default_currency") or "USD"
	cash_account = (
		frappe.db.get_value(
			"Account",
			{"account_type": "Cash", "company": company},
			"name",
		)
		or f"Cash - {abbr}"
	)
	cost_center = (
		frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
		or f"{company} - {abbr}"
	)
	warehouse_group = (
		frappe.db.get_value("Warehouse", {"is_group": 1, "company": company}, "name")
		or f"All Warehouses - {abbr}"
	)
	price_list = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name") or "Standard Selling"
	doc = frappe.get_doc(
		{
			"doctype": "Station",
			"station_code": code,
			"station_name": f"Test Station {code}",
			"company": company,
			"station_group": group,
			"country": "Kenya",
			"ownership_type": "Company-owned",
			"timezone": "Africa/Nairobi",
			"warehouse_group": warehouse_group,
			"price_list": price_list,
			"cost_center": cost_center,
			"safe_account": cash_account,
			"till_accounts": [{"currency": currency, "account": cash_account}],
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def make_fuel_item(item_code: str = "TEST-PMS", **kwargs) -> frappe.Document:
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": "Products",
			"stock_uom": "Litre",
			"fms_is_fuel": 1,
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def make_fuel_tank(
	station: str | None = None,
	tank_code: str = "T1",
	item: str | None = None,
	**kwargs,
) -> frappe.Document:
	if not station:
		station = make_station().name
	if not item:
		item = make_fuel_item().name
	name = f"{station}-{tank_code}"
	if frappe.db.exists("Fuel Tank", name):
		return frappe.get_doc("Fuel Tank", name)
	doc = frappe.get_doc(
		{
			"doctype": "Fuel Tank",
			"station": station,
			"tank_code": tank_code,
			"item": item,
			"capacity_l": 30000,
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def make_pump(
	station: str | None = None,
	pump_code: str = "P01",
	**kwargs,
) -> frappe.Document:
	if not station:
		station = make_station().name
	name = f"{station}-{pump_code}"
	if frappe.db.exists("Pump", name):
		return frappe.get_doc("Pump", name)
	doc = frappe.get_doc(
		{
			"doctype": "Pump",
			"station": station,
			"pump_code": pump_code,
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def make_nozzle(
	pump: str | None = None,
	tank: str | None = None,
	nozzle_no: int = 1,
	**kwargs,
) -> frappe.Document:
	if not pump:
		pump = make_pump().name
	if not tank:
		station = frappe.db.get_value("Pump", pump, "station")
		tank = make_fuel_tank(station=station).name
	doc = frappe.get_doc(
		{
			"doctype": "Nozzle",
			"pump": pump,
			"tank": tank,
			"nozzle_no": nozzle_no,
			**kwargs,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc
