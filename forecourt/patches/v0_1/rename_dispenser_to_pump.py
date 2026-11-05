"""Rename Dispenser to Pump.

Runs pre_model_sync so tabDispenser still exists at this point.
After this patch migrate will create tabPump from pump.json and
tabNozzle will have the pump column in place.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	# Abort if Dispenser records exist — manual cleanup required first.
	if frappe.db.table_exists("tabDispenser"):
		count = frappe.db.sql("SELECT COUNT(*) FROM `tabDispenser`")[0][0]
		if count:
			frappe.throw(
				f"Cannot rename Dispenser to Pump: tabDispenser has {count} row(s). "
				"Delete all Dispenser records first."
			)
		frappe.db.sql("DROP TABLE `tabDispenser`")

	# Remove the DocType record so Frappe does not try to sync it.
	for dt in ("Dispenser",):
		if frappe.db.exists("DocType", dt):
			frappe.db.delete("DocField", {"parent": dt})
			frappe.db.delete("DocType", {"name": dt})

	# Rename the foreign-key column in tabNozzle.
	if frappe.db.table_exists("tabNozzle") and frappe.db.has_column("tabNozzle", "dispenser"):
		frappe.db.sql(
			"ALTER TABLE `tabNozzle` CHANGE COLUMN `dispenser` `pump` VARCHAR(140) NULL DEFAULT NULL"
		)
