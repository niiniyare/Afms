# Tests for FMS-C14: station setup end to end
from __future__ import annotations

import frappe

from forecourt.tests.factories import (
	FMSTestCase,
	make_fuel_tank,
	make_nozzle,
	make_pump,
	make_station,
)


class TestStationSetup(FMSTestCase):
	def test_fuel_tank_creates_warehouse(self) -> None:
		station = make_station(code="KE-TST-WH")
		tank = make_fuel_tank(station=station.name, tank_code="T1")
		self.assertTrue(tank.warehouse, "Warehouse not set on Fuel Tank")
		self.assertTrue(frappe.db.exists("Warehouse", tank.warehouse))

	def test_fuel_tank_refuses_non_fuel_item(self) -> None:
		station = make_station(code="KE-TST-NF")
		if not frappe.db.exists("Item", "NON-FUEL-TST"):
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "NON-FUEL-TST",
					"item_name": "NON-FUEL-TST",
					"item_group": "Products",
					"stock_uom": "Nos",
					"fms_is_fuel": 0,
				}
			)
			item.flags.ignore_permissions = True
			item.insert()
		with self.assertRaises(frappe.ValidationError):
			make_fuel_tank(station=station.name, tank_code="T9", item="NON-FUEL-TST")

	def test_nozzle_name_format(self) -> None:
		station = make_station(code="KE-TST-NZ")
		pump = make_pump(station=station.name, pump_code="P01")
		tank = make_fuel_tank(station=station.name, tank_code="T1")
		nozzle = make_nozzle(pump=pump.name, tank=tank.name, nozzle_no=1)
		self.assertEqual(nozzle.name, f"{pump.name}-N1")

	def test_pump_station_mismatch_refused(self) -> None:
		"""Nozzle tank must belong to the same station as the pump."""
		s1 = make_station(code="KE-TST-S1")
		s2 = make_station(code="KE-TST-S2")
		pump = make_pump(station=s1.name, pump_code="P01")
		tank_s2 = make_fuel_tank(station=s2.name, tank_code="T1")
		with self.assertRaises(frappe.ValidationError):
			make_nozzle(pump=pump.name, tank=tank_s2.name, nozzle_no=1)

	def test_fuel_tank_capacity_must_be_positive(self) -> None:
		station = make_station(code="KE-TST-CAP")
		with self.assertRaises(frappe.ValidationError):
			make_fuel_tank(station=station.name, tank_code="T1", capacity_l=0)
