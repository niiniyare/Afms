"""Update stored meter label values to shortened forms.

Renames "Elec Meter" -> "Elec Mtr" and "Man Meter" -> "Man Mtr" in
Forecourt Settings (tabSingles) and Station records (tabStation).
"""

from __future__ import annotations

import frappe

_RENAMES = [("Elec Meter", "Elec Mtr"), ("Man Meter", "Man Mtr")]


def execute() -> None:
	for old, new in _RENAMES:
		frappe.db.sql(
			"UPDATE `tabSingles` SET value = %s WHERE doctype = %s AND field = %s AND value = %s",
			(new, "Forecourt Settings", "sales_basis", old),
		)

	if frappe.db.table_exists("tabStation"):
		for old, new in _RENAMES:
			frappe.db.sql(
				"UPDATE `tabStation` SET sales_basis = %s WHERE sales_basis = %s",
				(new, old),
			)
