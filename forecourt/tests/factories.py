"""
Test factories for FMS integration tests.

Each function inserts a minimal valid record and returns the doc.
Tests that need different values pass overrides via kwargs.
Never leave persistent state — use FMSTestCase which rolls back.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class FMSTestCase(FrappeTestCase):
	"""Base class for FMS integration tests. Rolls back after each test."""

	pass


def make_station_group(name: str = "KE", **kwargs) -> frappe.Document:
	if frappe.db.exists("Station Group", name):
		return frappe.get_doc("Station Group", name)
	doc = frappe.get_doc(
		{
			"doctype": "Station Group",
			"group_name": name,
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
		company = frappe.defaults.get_defaults().get("company") or frappe.get_all("Company", limit=1)[0].name
	if not group:
		group = make_station_group().name
	doc = frappe.get_doc(
		{
			"doctype": "Station",
			"station_code": code,
			"station_name": f"Test Station {code}",
			"company": company,
			"station_group": group,
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
