import frappe
from frappe import _


def create_tank_warehouse(tank_doc: "frappe.Document") -> None:
	"""Create the Warehouse for a newly inserted Fuel Tank.

	Allowed to use ignore_permissions — this is setup/ code creating a record
	as a side effect of inserting a master (per CLAUDE.md rule 6).
	"""
	station = frappe.get_cached_doc("Station", tank_doc.station)
	if not station.warehouse_group:
		frappe.throw(
			_("Station {0} has no Warehouse Group. Set it before creating tanks.").format(tank_doc.station)
		)
	warehouse_name = f"{tank_doc.tank_code} - {tank_doc.station}"
	warehouse = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": warehouse_name,
			"parent_warehouse": station.warehouse_group,
			"company": tank_doc.company,
			"is_group": 0,
		}
	)
	warehouse.flags.ignore_permissions = True
	warehouse.insert()
	frappe.db.set_value("Fuel Tank", tank_doc.name, "warehouse", warehouse.name)
	tank_doc.warehouse = warehouse.name
