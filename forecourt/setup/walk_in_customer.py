"""Create the walk-in customer for a newly inserted Station.

Called from Station.after_insert() with ignore_permissions so a
Forecourt Administrator (who may lack Customer create rights) can
set up a new station.
"""

from __future__ import annotations

import frappe
from frappe import _


def create_walk_in_customer(station_doc: "frappe.Document") -> None:
	"""Insert a Walk-in customer for *station_doc* and back-link it.

	Idempotent: skips creation if the customer already exists.
	Uses ignore_permissions (permitted in setup/ per CLAUDE.md rule 6).
	"""
	customer_name = f"Walk-in – {station_doc.station_name}"  # noqa: RUF001  # noqa: RUF001

	if frappe.db.exists("Customer", customer_name):
		frappe.db.set_value("Station", station_doc.name, "walk_in_customer", customer_name)
		return

	configured_group = frappe.db.get_single_value("Selling Settings", "customer_group")
	if configured_group and not frappe.db.get_value("Customer Group", configured_group, "is_group"):
		default_group = configured_group
	else:
		default_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "Individual"
	default_territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"

	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Individual",
			"customer_group": default_group,
			"territory": default_territory,
			"fms_is_walk_in": 1,
			"fms_station": station_doc.name,
		}
	)
	customer.flags.ignore_permissions = True
	customer.insert()

	frappe.db.set_value("Station", station_doc.name, "walk_in_customer", customer.name)
